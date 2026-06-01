from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from discordbot.cards import render_deadlock_profile_card
from discordbot.deadlock import (
    DeadlockAPI,
    DeadlockError,
    DeadlockPlayer,
    friendly_rank_name,
    format_kda,
    format_ratio,
    format_unix_ts,
)


REM_IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "rem.png"


class DeadlockPlayerSelect(discord.ui.Select):
    def __init__(
        self,
        cog: "Deadlock",
        requester_id: int,
        action: str,
        players: list[DeadlockPlayer],
    ) -> None:
        self.cog = cog
        self.requester_id = requester_id
        self.action = action
        self.players = players
        options = [
            discord.SelectOption(
                label=player.personaname[:100],
                value=str(index),
                description=f"ID {player.account_id}"[:100],
            )
            for index, player in enumerate(players[:5])
        ]
        super().__init__(
            placeholder="Choose the correct Deadlock player",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the person who ran this command can pick the player.",
                ephemeral=True,
            )
            return

        player = self.players[int(self.values[0])]
        if self.action == "profile":
            await self.cog.send_profile(interaction, player)
        else:
            await self.cog.send_recent(interaction, player)
        self.view.stop()


class DeadlockPlayerChoiceView(discord.ui.View):
    def __init__(
        self,
        cog: "Deadlock",
        requester_id: int,
        action: str,
        players: list[DeadlockPlayer],
    ) -> None:
        super().__init__(timeout=60)
        self.add_item(DeadlockPlayerSelect(cog, requester_id, action, players))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


class Deadlock(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.api = DeadlockAPI()

    @app_commands.command(name="deadlocksearch", description="Search for a Deadlock player.")
    async def deadlock_search(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            players = await self.api.search_players(query)
        except DeadlockError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        if not players:
            await interaction.followup.send("No Deadlock players found for that search.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Deadlock Player Search",
            description="Use an account ID from below with `/deadlockprofile` or `/deadlockrecent`.",
            color=discord.Color.dark_teal(),
        )
        for player in players[:5]:
            label = f"{player.personaname} - `{player.account_id}`"
            details = player.profileurl
            if player.countrycode:
                details += f"\nCountry: {player.countrycode}"
            details += f"\nUpdated: {format_unix_ts(player.last_updated)}"
            embed.add_field(name=label, value=details, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="deadlockprofile", description="Show a Deadlock player's profile stats.")
    async def deadlock_profile(self, interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            resolution = await self._resolve_player(player)
        except DeadlockError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        if isinstance(resolution, list):
            await interaction.followup.send(
                embed=self._ambiguous_player_embed("profile", player, resolution),
                view=DeadlockPlayerChoiceView(self, interaction.user.id, "profile", resolution),
                ephemeral=True,
            )
            return

        await self.send_profile(interaction, resolution)

    @app_commands.command(name="deadlockrecent", description="Show a Deadlock player's recent matches.")
    async def deadlock_recent(self, interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            resolution = await self._resolve_player(player)
        except DeadlockError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        if isinstance(resolution, list):
            await interaction.followup.send(
                embed=self._ambiguous_player_embed("recent matches", player, resolution),
                view=DeadlockPlayerChoiceView(self, interaction.user.id, "recent", resolution),
                ephemeral=True,
            )
            return

        await self.send_recent(interaction, resolution)

    async def send_profile(self, interaction: discord.Interaction, selected: DeadlockPlayer) -> None:
        rank = await self.api.get_player_rank(selected.account_id)
        hero_info = await self.api.get_hero_info()
        hero_stats = await self.api.get_hero_stats(selected.account_id)
        top_heroes = hero_stats[:3]
        rank_name = friendly_rank_name(rank.rank) if rank else "Unknown"
        rating_text = f"{(rank.player_score or 0):.2f}" if rank else "0.00"
        card_buffer = await render_deadlock_profile_card(
            player=selected,
            rank_name=rank_name,
            internal_rating=rating_text,
            top_heroes=top_heroes,
            hero_info=hero_info,
            rem_path=REM_IMAGE_PATH,
            cache_updated_ts=selected.last_updated,
        )

        embed = discord.Embed(
            title=f"Deadlock Profile: {selected.personaname}",
            url=selected.profileurl,
            color=discord.Color.dark_gold(),
        )
        embed.set_image(url="attachment://deadlock-profile.png")
        if top_heroes:
            hero_summary = ", ".join(
                hero_info.get(stat.hero_id).name if hero_info.get(stat.hero_id) else f"Hero {stat.hero_id}"
                for stat in top_heroes
            )
            embed.description = f"Top hero snapshot: {hero_summary}"

        card_file = discord.File(card_buffer, filename="deadlock-profile.png")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=card_file)
        else:
            await interaction.response.send_message(embed=embed, file=card_file)

    async def send_recent(self, interaction: discord.Interaction, selected: DeadlockPlayer) -> None:
        hero_names = await self.api.get_hero_names()
        matches = await self.api.get_match_history(selected.account_id, limit=5)

        embed = discord.Embed(
            title=f"Recent Deadlock Matches: {selected.personaname}",
            url=selected.profileurl,
            color=discord.Color.dark_blue(),
        )
        if selected.avatarfull:
            embed.set_thumbnail(url=selected.avatarfull)
        embed.set_image(url="attachment://rem.png")

        for match in matches:
            hero_name = hero_names.get(match.hero_id, f"Hero {match.hero_id}")
            result = "Win" if match.match_result == 1 else "Loss"
            kda = f"{match.player_kills or 0}/{match.player_deaths or 0}/{match.player_assists or 0}"
            value = (
                f"{result} - {kda}\n"
                f"Duration: `{self._format_seconds(match.match_duration_s)}` | "
                f"Net Worth: `{match.net_worth or 0}` | Last Hits: `{match.last_hits or 0}`\n"
                f"Played: {format_unix_ts(match.start_time)}"
            )
            embed.add_field(name=f"{hero_name} - Match `{match.match_id}`", value=value, inline=False)

        await self._send_embed_with_rem(interaction, embed)

    async def _resolve_player(self, player: str) -> DeadlockPlayer | list[DeadlockPlayer]:
        resolved_input = await self.api.resolve_steam_profile_input(player)
        cleaned = str(resolved_input).strip()
        if cleaned.isdigit():
            account_id = int(cleaned)
            profiles = await self.api.search_players(cleaned)
            for profile in profiles:
                if profile.account_id == account_id:
                    return profile
            return DeadlockPlayer(
                account_id=account_id,
                personaname=cleaned,
                profileurl=f"https://steamcommunity.com/profiles/{cleaned}",
                avatarfull=None,
                countrycode=None,
                last_updated=None,
            )

        profiles = await self.api.search_players(cleaned)
        if not profiles:
            raise DeadlockError("No Deadlock player matched that search.")

        exact_matches = [
            profile for profile in profiles if profile.personaname.casefold() == cleaned.casefold()
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(profiles) == 1:
            return profiles[0]
        return profiles[:5]

    def _ambiguous_player_embed(
        self,
        action_name: str,
        query: str,
        players: list[DeadlockPlayer],
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Choose the Right Deadlock Player",
            description=(
                f"Multiple players matched `{query}`. Pick one below or rerun the command with an account ID.\n"
                f"This selection will open {action_name}."
            ),
            color=discord.Color.orange(),
        )
        for player in players[:5]:
            value = f"`{player.account_id}`\n{player.profileurl}"
            if player.avatarfull:
                value += f"\n[Avatar]({player.avatarfull})"
            embed.add_field(name=player.personaname, value=value, inline=False)
        return embed

    def _format_seconds(self, seconds: int | None) -> str:
        if not seconds:
            return "Unknown"
        minutes, secs = divmod(int(seconds), 60)
        return f"{minutes}:{secs:02d}"

    async def _send_embed_with_rem(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
    ) -> None:
        rem_file = discord.File(REM_IMAGE_PATH, filename="rem.png")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=rem_file)
        else:
            await interaction.response.send_message(embed=embed, file=rem_file)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Deadlock(bot))
