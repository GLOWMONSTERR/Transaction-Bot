"""Configuration utilities for the Discord bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

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


def _get_int_list(name: str) -> Tuple[int, ...]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return ()

    ids = []
    for part in value.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        try:
            ids.append(int(stripped))
        except ValueError as exc:  # pragma: no cover - defensive programming
            raise ValueError(
                f"Environment variable {name} must be a comma-separated list of integers"
            ) from exc

    return tuple(ids)


@dataclass(frozen=True)
class BotConfig:
    """Runtime configuration for the Discord bot."""

    token: str
    guild_id: Optional[int]
    captain_role_id: Optional[int]
    co_captain_role_id: Optional[int]
    team_member_role_id: Optional[int]
    transactions_channel_id: Optional[int]
    match_category_id: Optional[int]
    match_results_channel_id: Optional[int]
    match_assignments_channel_id: Optional[int]
    match_staff_alert_channel_id: Optional[int]
    caster_role_id: Optional[int]
    ref_role_id: Optional[int]
    mod_role_id: Optional[int]
    admin_role_ids: Tuple[int, ...]
    challonge_username: Optional[str]
    challonge_api_key: Optional[str]
    challonge_tournament: Optional[str]
    web_host: Optional[str]
    web_port: Optional[int]

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
            transactions_channel_id=_get_int("TRANSACTIONS_CHANNEL_ID"),
            match_category_id=_get_int("MATCH_CATEGORY_ID"),
            match_results_channel_id=_get_int("MATCH_RESULTS_CHANNEL_ID"),
            match_assignments_channel_id=_get_int("MATCH_ASSIGNMENTS_CHANNEL_ID"),
            match_staff_alert_channel_id=_get_int("MATCH_STAFF_ALERT_CHANNEL_ID"),
            caster_role_id=_get_int("CASTER_ROLE_ID"),
            ref_role_id=_get_int("REF_ROLE_ID"),
            mod_role_id=_get_int("MOD_ROLE_ID"),
            admin_role_ids=_get_int_list("ADMIN_ROLE_IDS"),
            challonge_username=os.getenv("CHALLONGE_USERNAME"),
            challonge_api_key=os.getenv("CHALLONGE_API_KEY"),
            challonge_tournament=os.getenv("CHALLONGE_TOURNAMENT"),
            web_host=os.getenv("WEB_HOST"),
            web_port=_get_int("WEB_PORT"),
        )
