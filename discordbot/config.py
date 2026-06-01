from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    discord_token: str
    command_prefix: str = "!"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Missing DISCORD_TOKEN. Add it to your environment or .env file."
            )

        prefix = os.getenv("COMMAND_PREFIX", "!").strip() or "!"
        return cls(
            discord_token=token,
            command_prefix=prefix,
        )
