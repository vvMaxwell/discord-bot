from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import deque
from dataclasses import dataclass
from typing import Deque

import discord
import imageio_ffmpeg
import yt_dlp


LOGGER = logging.getLogger(__name__)

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch1",
}

YTDL_AUTOCOMPLETE_OPTIONS = {
    "quiet": True,
    "skip_download": True,
    "extract_flat": True,
    "default_search": "ytsearch5",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "Live"

    total_seconds = int(seconds)

    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_ffmpeg_executable() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


@dataclass(slots=True)
class Song:
    title: str
    stream_url: str
    webpage_url: str
    duration: int | None
    thumbnail: str | None
    requester_id: int
    requester_name: str
    source_label: str = "YouTube"

    @property
    def duration_label(self) -> str:
        return format_duration(self.duration)


@dataclass(slots=True)
class SearchResult:
    title: str
    webpage_url: str
    duration: int | float | None
    channel_name: str | None

    @property
    def duration_label(self) -> str:
        return format_duration(self.duration)


async def create_song(query: str, requester: discord.abc.User) -> Song:
    loop = asyncio.get_running_loop()

    def extract() -> dict:
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ytdl:
            target = query if URL_PATTERN.match(query) else f"ytsearch1:{query}"
            info = ytdl.extract_info(target, download=False)
            if "entries" in info:
                return info["entries"][0]
            return info

    data = await loop.run_in_executor(None, extract)
    return Song(
        title=data.get("title", "Unknown title"),
        stream_url=data["url"],
        webpage_url=data.get("webpage_url", query),
        duration=data.get("duration"),
        thumbnail=data.get("thumbnail"),
        requester_id=requester.id,
        requester_name=requester.display_name,
        source_label="YouTube",
    )


def _trim_choice(value: str, limit: int = 100) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


async def search_youtube_results(query: str, limit: int = 5) -> list[SearchResult]:
    cleaned = query.strip()
    if len(cleaned) < 2:
        return []

    loop = asyncio.get_running_loop()

    def extract() -> list[SearchResult]:
        with yt_dlp.YoutubeDL(YTDL_AUTOCOMPLETE_OPTIONS) as ytdl:
            info = ytdl.extract_info(f"ytsearch{limit}:{cleaned}", download=False)
            entries = info.get("entries") or []
            results: list[SearchResult] = []
            for entry in entries[:limit]:
                if not entry:
                    continue
                title = entry.get("title")
                webpage_url = entry.get("url") or entry.get("webpage_url")
                if not title or not webpage_url:
                    continue
                results.append(
                    SearchResult(
                        title=title,
                        webpage_url=webpage_url,
                        duration=entry.get("duration"),
                        channel_name=entry.get("uploader"),
                    )
                )
            return results

    try:
        return await loop.run_in_executor(None, extract)
    except Exception:
        LOGGER.debug("Search lookup failed for query %r", cleaned, exc_info=True)
        return []


class GuildMusicState:
    def __init__(self, bot: discord.Client, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        self.queue: Deque[Song] = deque()
        self.current: Song | None = None
        self.loop_current = False
        self.volume = 0.5
        self.lock = asyncio.Lock()

    async def enqueue(self, guild: discord.Guild, song: Song) -> bool:
        async with self.lock:
            should_start = not (
                guild.voice_client
                and (guild.voice_client.is_playing() or guild.voice_client.is_paused())
            )
            self.queue.append(song)
            if should_start:
                await self._play_next(guild)
            return should_start

    async def skip(self, guild: discord.Guild) -> bool:
        voice = guild.voice_client
        if not voice or not (voice.is_playing() or voice.is_paused()):
            return False
        voice.stop()
        return True

    async def stop(self, guild: discord.Guild) -> None:
        async with self.lock:
            self.queue.clear()
            self.current = None
            if guild.voice_client:
                guild.voice_client.stop()

    async def _after_song(self, guild: discord.Guild, error: Exception | None) -> None:
        if error:
            LOGGER.exception("Playback error in guild %s", guild.id, exc_info=error)
        async with self.lock:
            await self._play_next(guild)

    async def _play_next(self, guild: discord.Guild) -> None:
        voice = guild.voice_client
        if not voice or not voice.is_connected():
            self.current = None
            return

        if self.loop_current and self.current is not None:
            next_song = self.current
        elif self.queue:
            next_song = self.queue.popleft()
            self.current = next_song
        else:
            self.current = None
            return

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                next_song.stream_url,
                executable=get_ffmpeg_executable(),
                **FFMPEG_OPTIONS,
            ),
            volume=self.volume,
        )

        def after_playback(error: Exception | None) -> None:
            asyncio.run_coroutine_threadsafe(
                self._after_song(guild, error),
                self.bot.loop,
            )

        voice.play(source, after=after_playback)

    def queue_snapshot(self) -> list[Song]:
        return list(self.queue)

    def shuffle(self) -> None:
        items = list(self.queue)
        random.shuffle(items)
        self.queue = deque(items)


class MusicStateStore:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}

    def get(self, guild_id: int) -> GuildMusicState:
        state = self._states.get(guild_id)
        if state is None:
            state = GuildMusicState(self.bot, guild_id)
            self._states[guild_id] = state
        return state

    def remove(self, guild_id: int) -> None:
        self._states.pop(guild_id, None)
