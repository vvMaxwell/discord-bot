from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


def nice_dt(dt) -> str:
    if dt is None:
        return "Unknown"
    return discord.utils.format_dt(dt, style="F")


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Show the bot's main commands.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Bot Commands",
            description="A mix of music controls, server utilities, and friend-group chaos.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Music",
            value="/join, /play, /pause, /resume, /skip, /queue, /nowplaying, /shuffle, /loop, /volume, /leave\nUse /play with a search term to choose a YouTube result, or paste a YouTube URL to play immediately.",
            inline=False,
        )
        embed.add_field(
            name="General",
            value="/ping, /userinfo, /serverinfo, /avatar, /poll",
            inline=False,
        )
        embed.add_field(
            name="Fun",
            value="/coinflip, /roll, /choose, /8ball, /ship, /memeify, /compliment, /roast, /rps, /truthordare, /wouldyourather, /rate",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Check whether the bot is alive.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! `{latency_ms}ms`")

    @app_commands.command(name="userinfo", description="Show info about a server member.")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=target.display_name,
            color=target.color if target.color.value else discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Username", value=str(target), inline=True)
        embed.add_field(name="ID", value=str(target.id), inline=True)
        embed.add_field(name="Joined Server", value=nice_dt(target.joined_at), inline=False)
        embed.add_field(name="Created Account", value=nice_dt(target.created_at), inline=False)
        roles = [role.mention for role in reversed(target.roles[1:6])]
        embed.add_field(
            name="Top Roles",
            value=", ".join(roles) if roles else "No special roles",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Show info about this server.")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=guild.name, color=discord.Color.green())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Created", value=nice_dt(guild.created_at), inline=False)
        embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
        embed.add_field(name="Emoji Count", value=str(len(guild.emojis)), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's avatar.")
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        embed = discord.Embed(
            title=f"{target.display_name}'s avatar",
            color=discord.Color.random(),
        )
        embed.set_image(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll", description="Create a quick reaction poll.")
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option_one: str,
        option_two: str,
        option_three: str | None = None,
        option_four: str | None = None,
    ) -> None:
        options = [option_one, option_two, option_three, option_four]
        cleaned = [option for option in options if option]
        emoji_numbers = ["1\N{variation selector-16}\N{combining enclosing keycap}", "2\N{variation selector-16}\N{combining enclosing keycap}", "3\N{variation selector-16}\N{combining enclosing keycap}", "4\N{variation selector-16}\N{combining enclosing keycap}"]

        embed = discord.Embed(
            title="Poll",
            description=question,
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Started by {interaction.user.display_name}")
        for emoji, option in zip(emoji_numbers, cleaned, strict=False):
            embed.add_field(name=emoji, value=option, inline=False)

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for emoji in emoji_numbers[: len(cleaned)]:
            await message.add_reaction(emoji)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
