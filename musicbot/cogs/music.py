from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from musicbot.music import MusicStateStore, SearchResult, create_song, search_youtube_results


async def play_query_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    # Keep a lightweight autocomplete handler so clients with cached command metadata
    # do not hit a signature mismatch while Discord refreshes the schema.
    current = current.strip()
    if not current:
        return []

    suggestions = [
        current,
        f"{current} official audio",
        f"{current} lyrics",
        f"{current} live",
    ]
    seen: set[str] = set()
    choices: list[app_commands.Choice[str]] = []
    for suggestion in suggestions:
        if suggestion in seen:
            continue
        seen.add(suggestion)
        choices.append(app_commands.Choice(name=suggestion[:100], value=suggestion))
    return choices[:5]


class SearchChoiceSelect(discord.ui.Select):
    def __init__(
        self,
        cog: "Music",
        requester_id: int,
        results: list[SearchResult],
    ) -> None:
        self.cog = cog
        self.requester_id = requester_id
        self.results = results
        options = [
            discord.SelectOption(
                label=result.title[:100],
                value=str(index),
                description=(
                    f"{result.duration_label} - {result.channel_name}"[:100]
                    if result.channel_name
                    else result.duration_label
                ),
            )
            for index, result in enumerate(results)
        ]
        super().__init__(
            placeholder="Choose a song to play",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the person who ran `/play` can use this picker.",
                ephemeral=True,
            )
            return

        selected = self.results[int(self.values[0])]
        await self.cog.play_selected_result(interaction, selected.webpage_url)
        self.view.stop()


class SearchChoiceView(discord.ui.View):
    def __init__(
        self,
        cog: "Music",
        requester_id: int,
        results: list[SearchResult],
    ) -> None:
        super().__init__(timeout=60)
        self.add_item(SearchChoiceSelect(cog, requester_id, results))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.states = MusicStateStore(bot)

    async def ensure_voice(
        self, interaction: discord.Interaction
    ) -> tuple[discord.Guild, discord.Member, discord.VoiceChannel] | None:
        guild = interaction.guild
        user = interaction.user
        if guild is None or not isinstance(user, discord.Member):
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return None

        if user.voice is None or user.voice.channel is None:
            await interaction.response.send_message(
                "Join a voice channel first.",
                ephemeral=True,
            )
            return None

        if not isinstance(user.voice.channel, discord.VoiceChannel):
            await interaction.response.send_message(
                "Please join a standard voice channel.",
                ephemeral=True,
            )
            return None

        return guild, user, user.voice.channel

    @app_commands.command(name="join", description="Join your current voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        voice_context = await self.ensure_voice(interaction)
        if voice_context is None:
            return
        guild, _, channel = voice_context

        if guild.voice_client and guild.voice_client.channel == channel:
            await interaction.response.send_message("I'm already in your voice channel.")
            return

        if guild.voice_client:
            await guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        await interaction.response.send_message(f"Joined **{channel.name}**.")

    @app_commands.command(name="play", description="Play a song from a URL or search term.")
    @app_commands.describe(query="A YouTube URL or song name")
    @app_commands.autocomplete(query=play_query_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        voice_context = await self.ensure_voice(interaction)
        if voice_context is None:
            return
        query = query.strip()
        if query.startswith("http://") or query.startswith("https://"):
            await self.play_selected_result(interaction, query)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        results = await search_youtube_results(query, limit=5)
        if not results:
            await interaction.followup.send(
                "I couldn't find any results for that search.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Choose a Result",
            description="Pick one of these YouTube results to add it to the queue.",
            color=discord.Color.blurple(),
        )
        for index, result in enumerate(results, start=1):
            label = f"`{index}.` [{result.title}]({result.webpage_url})"
            details = result.duration_label
            if result.channel_name:
                details += f" - {result.channel_name}"
            embed.add_field(name=label, value=details, inline=False)
        await interaction.followup.send(
            embed=embed,
            view=SearchChoiceView(self, interaction.user.id, results),
            ephemeral=True,
        )

    async def play_selected_result(
        self,
        interaction: discord.Interaction,
        query: str,
    ) -> None:
        voice_context = await self.ensure_voice(interaction)
        if voice_context is None:
            return
        guild, member, channel = voice_context

        if interaction.response.is_done():
            sender = interaction.followup.send
        else:
            await interaction.response.defer(thinking=True)
            sender = interaction.followup.send

        try:
            if guild.voice_client is None:
                await channel.connect()
            elif guild.voice_client.channel != channel:
                await guild.voice_client.move_to(channel)

            state = self.states.get(guild.id)
            song = await create_song(query, member)
            started = await state.enqueue(guild, song)
        except Exception:
            await sender(
                "I couldn't load that track. Try a different search or URL.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Now playing" if started else "Added to queue",
            description=f"[{song.title}]({song.webpage_url})",
            color=discord.Color.red(),
        )
        embed.add_field(name="Length", value=song.duration_label, inline=True)
        embed.add_field(name="Requested by", value=member.mention, inline=True)
        embed.add_field(name="Source", value=song.source_label, inline=True)
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        await sender(embed=embed)

    @app_commands.command(name="pause", description="Pause the current song.")
    async def pause(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or guild.voice_client is None or not guild.voice_client.is_playing():
            await interaction.response.send_message(
                "Nothing is playing right now.",
                ephemeral=True,
            )
            return
        guild.voice_client.pause()
        await interaction.response.send_message("Paused playback.")

    @app_commands.command(name="resume", description="Resume the current song.")
    async def resume(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or guild.voice_client is None or not guild.voice_client.is_paused():
            await interaction.response.send_message(
                "Nothing is paused right now.",
                ephemeral=True,
            )
            return
        guild.voice_client.resume()
        await interaction.response.send_message("Resumed playback.")

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return
        state = self.states.get(guild.id)
        skipped = await state.skip(guild)
        if not skipped:
            await interaction.response.send_message(
                "Nothing to skip right now.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message("Skipped the current song.")

    @app_commands.command(name="queue", description="Show the current music queue.")
    async def queue(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        state = self.states.get(guild.id)
        embed = discord.Embed(title="Music Queue", color=discord.Color.blurple())

        if state.current:
            embed.add_field(
                name="Now playing",
                value=(
                    f"[{state.current.title}]({state.current.webpage_url}) - "
                    f"{state.current.duration_label} ({state.current.source_label})"
                ),
                inline=False,
            )

        upcoming = state.queue_snapshot()
        if not upcoming:
            embed.description = "The queue is empty."
        else:
            lines = [
                f"`{index}.` [{song.title}]({song.webpage_url}) - {song.duration_label} ({song.source_label})"
                for index, song in enumerate(upcoming[:10], start=1)
            ]
            if len(upcoming) > 10:
                lines.append(f"...and {len(upcoming) - 10} more.")
            embed.add_field(name="Up next", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the current song.")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        state = self.states.get(guild.id)
        if state.current is None:
            await interaction.response.send_message(
                "Nothing is playing right now.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{state.current.title}]({state.current.webpage_url})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Length", value=state.current.duration_label, inline=True)
        embed.add_field(name="Requested by", value=state.current.requester_name, inline=True)
        embed.add_field(name="Source", value=state.current.source_label, inline=True)
        if state.current.thumbnail:
            embed.set_thumbnail(url=state.current.thumbnail)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return
        state = self.states.get(guild.id)
        if len(state.queue_snapshot()) < 2:
            await interaction.response.send_message(
                "Need at least two queued songs to shuffle.",
                ephemeral=True,
            )
            return
        state.shuffle()
        await interaction.response.send_message("Shuffled the queue.")

    @app_commands.command(name="loop", description="Toggle looping the current song.")
    async def loop(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return
        state = self.states.get(guild.id)
        state.loop_current = not state.loop_current
        await interaction.response.send_message(
            f"Looping is now **{'on' if state.loop_current else 'off'}**."
        )

    @app_commands.command(name="volume", description="Set playback volume.")
    async def volume(
        self,
        interaction: discord.Interaction,
        percent: app_commands.Range[int, 1, 200],
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return
        state = self.states.get(guild.id)
        state.volume = percent / 100
        if guild.voice_client and guild.voice_client.source:
            guild.voice_client.source.volume = state.volume
        await interaction.response.send_message(f"Volume set to **{percent}%**.")

    @app_commands.command(name="leave", description="Disconnect and clear the queue.")
    async def leave(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or guild.voice_client is None:
            await interaction.response.send_message(
                "I'm not in a voice channel.",
                ephemeral=True,
            )
            return

        state = self.states.get(guild.id)
        await state.stop(guild)
        await guild.voice_client.disconnect()
        self.states.remove(guild.id)
        await interaction.response.send_message(
            "Left the voice channel and cleared the queue."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
