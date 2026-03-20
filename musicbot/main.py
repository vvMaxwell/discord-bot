from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from discord.errors import HTTPException, NotFound

from musicbot.config import Settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

DEV_GUILD_ID = 441312443638218762


class FriendsBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True

        super().__init__(
            command_prefix=settings.command_prefix,
            intents=intents,
            help_command=None,
        )
        self.settings = settings

    async def setup_hook(self) -> None:
        for extension in (
            "musicbot.cogs.general",
            "musicbot.cogs.fun",
            "musicbot.cogs.music",
        ):
            await self.load_extension(extension)

        dev_guild = discord.Object(id=DEV_GUILD_ID)
        self.tree.copy_global_to(guild=dev_guild)
        await self.tree.sync(guild=dev_guild)
        logging.info("Slash commands synced to guild %s.", DEV_GUILD_ID)

    async def on_ready(self) -> None:
        if self.user is None:
            return
        logging.info("Logged in as %s (%s)", self.user, self.user.id)


def build_bot() -> FriendsBot:
    settings = Settings.from_env()
    return FriendsBot(settings)


def main() -> None:
    bot = build_bot()

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        original_error = getattr(error, "original", error)
        if interaction.response.is_done():
            responder = interaction.followup.send
        else:
            responder = interaction.response.send_message

        if isinstance(error, app_commands.CommandOnCooldown):
            await responder(
                f"That command is cooling down. Try again in {error.retry_after:.1f}s.",
                ephemeral=True,
            )
            return

        if isinstance(error, app_commands.MissingPermissions):
            await responder(
                "You do not have permission to use that command.",
                ephemeral=True,
            )
            return

        if isinstance(original_error, (NotFound, HTTPException)):
            logging.warning("Interaction expired before a response could be sent.")
            return

        logging.exception("App command failed", exc_info=error)
        await responder(
            "Something went wrong while running that command.",
            ephemeral=True,
        )

    bot.run(bot.settings.discord_token, log_handler=None)
