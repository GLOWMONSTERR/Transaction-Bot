"""Match scheduling and persistence utilities."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@dataclass
class Match:
    """Represents a scheduled match between two teams."""

    id: str
    team_one: str
    team_two: str
    channel_id: int
    due_at: str
    week: int
    reminder_sent: bool = False
    status: str = "open"  # open | completed | overdue
    scores: Dict[str, int] = field(default_factory=dict)
    rounds: List[str] = field(default_factory=list)
    submissions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    mismatch_attempts: int = 0
    scheduled_time: Optional[str] = None
    scheduled_confirmed: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "team_one": self.team_one,
            "team_two": self.team_two,
            "channel_id": self.channel_id,
            "due_at": self.due_at,
            "week": self.week,
            "reminder_sent": self.reminder_sent,
            "status": self.status,
            "scores": self.scores,
            "rounds": self.rounds,
            "submissions": self.submissions,
            "mismatch_attempts": self.mismatch_attempts,
            "scheduled_time": self.scheduled_time,
            "scheduled_confirmed": self.scheduled_confirmed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Match":
        return cls(
            id=data["id"],
            team_one=data["team_one"],
            team_two=data["team_two"],
            channel_id=int(data["channel_id"]),
            due_at=data["due_at"],
            week=int(data.get("week", 1)),
            reminder_sent=bool(data.get("reminder_sent", False)),
            status=data.get("status", "open"),
            scores={k: int(v) for k, v in data.get("scores", {}).items()},
            rounds=list(data.get("rounds", [])),
            submissions=dict(data.get("submissions", {})),
            mismatch_attempts=int(data.get("mismatch_attempts", 0)),
            scheduled_time=data.get("scheduled_time"),
            scheduled_confirmed=bool(data.get("scheduled_confirmed", False)),
        )

    def due_datetime(self) -> datetime:
        return datetime.strptime(self.due_at, ISO_FORMAT)


class MatchManager:
    """Handles match creation, updates, and persistence."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._matches: Dict[str, Match] = {}
        self.reload()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def reload(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write()
            return

        with self._path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self._matches = {match_dict["id"]: Match.from_dict(match_dict) for match_dict in payload.get("matches", [])}

    def _write(self) -> None:
        payload = {
            "matches": [match.to_dict() for match in self._matches.values()],
        }
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def save(self) -> None:
        self._write()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def all_matches(self) -> Iterable[Match]:
        return list(self._matches.values())

    def find_by_channel(self, channel_id: int) -> Optional[Match]:
        for match in self._matches.values():
            if match.channel_id == channel_id:
                return match
        return None

    def open_matches(self) -> Iterable[Match]:
        return [m for m in self._matches.values() if m.status == "open"]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def create_match(self, *, team_one: str, team_two: str, channel_id: int, due_at: datetime, week: int) -> Match:
        match = Match(
            id=str(uuid.uuid4()),
            team_one=team_one,
            team_two=team_two,
            channel_id=channel_id,
            due_at=due_at.strftime(ISO_FORMAT),
            week=week,
        )
        self._matches[match.id] = match
        self.save()
        return match

    def mark_reminded(self, match: Match) -> None:
        match.reminder_sent = True
        self._matches[match.id] = match
        self.save()

    def mark_completed(self, match: Match, *, scores: Dict[str, int], rounds: List[str]) -> None:
        match.status = "completed"
        match.scores = scores
        match.rounds = rounds
        match.submissions = {}
        match.mismatch_attempts = 0
        self._matches[match.id] = match
        self.save()

    def mark_overdue(self, match: Match) -> None:
        match.status = "overdue"
        self._matches[match.id] = match
        self.save()

    def set_scheduled_time(self, match: Match, *, scheduled_time: Optional[str], confirmed: bool = False) -> None:
        match.scheduled_time = scheduled_time
        match.scheduled_confirmed = confirmed
        self._matches[match.id] = match
        self.save()
