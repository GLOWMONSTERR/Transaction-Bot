"""Configuration utilities for the Discord bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"Environment variable {name} must be an integer") from exc


@dataclass(frozen=True)
class BotConfig:
    """Runtime configuration for the Discord bot."""

    token: str
    guild_id: Optional[int]
    captain_role_id: Optional[int]
    co_captain_role_id: Optional[int]
    team_member_role_id: Optional[int]

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_TOKEN must be set in the environment or .env file")

        return cls(
            token=token,
            guild_id=_get_int("GUILD_ID"),
            captain_role_id=_get_int("CAPTAIN_ROLE_ID"),
            co_captain_role_id=_get_int("CO_CAPTAIN_ROLE_ID"),
            team_member_role_id=_get_int("TEAM_MEMBER_ROLE_ID"),
        )
