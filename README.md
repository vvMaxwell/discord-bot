# Discord Music + Fun Bot

A Python Discord bot with music playback, fun friend-group commands, and general server utilities without moderation commands like ban or kick.

## Features

### Music

- `/join`
- `/play <query or YouTube url>`
- `/pause`
- `/resume`
- `/skip`
- `/queue`
- `/nowplaying`
- `/shuffle`
- `/loop`
- `/volume <1-200>`
- `/leave`

### Fun

- `/coinflip`
- `/roll`
- `/choose`
- `/8ball`
- `/ship`
- `/memeify`
- `/compliment`
- `/roast`
- `/rps`
- `/truthordare`
- `/wouldyourather`
- `/rate`

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`
4. Add your bot token to `DISCORD_TOKEN`
5. Install FFmpeg and make sure `ffmpeg` is available in your PATH
6. Run the bot:

```bash
python bot.py
```

## Notes

- Music playback uses `yt-dlp` to resolve audio streams.
- `/play` can search YouTube and let you choose a result directly inside Discord, or it can play a pasted YouTube URL immediately.
- Music commands are YouTube-focused right now.
- Slash commands may take a short moment to appear globally the first time.
- If you want to add more commands later, the code is split into cogs under `musicbot/cogs/`.
