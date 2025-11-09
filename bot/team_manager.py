"""Persistence layer for teams and invites."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class Team:
    """Represents a competitive team in the league."""

    name: str
    hex_color: str
    role_id: int
    captain_id: int
    icon_url: Optional[str] = None
    co_captains: List[int] = field(default_factory=list)
    members: List[int] = field(default_factory=list)
    invites: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "hex_color": self.hex_color,
            "role_id": self.role_id,
            "captain_id": self.captain_id,
            "icon_url": self.icon_url,
            "co_captains": self.co_captains,
            "members": self.members,
            "invites": self.invites,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Team":
        return cls(
            name=data["name"],
            hex_color=data["hex_color"],
            role_id=int(data["role_id"]),
            captain_id=int(data["captain_id"]),
            icon_url=data.get("icon_url"),
            co_captains=[int(uid) for uid in data.get("co_captains", [])],
            members=[int(uid) for uid in data.get("members", [])],
            invites=[int(uid) for uid in data.get("invites", [])],
        )


class TeamManager:
    """Handles reading and writing team metadata to disk."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._teams: Dict[str, Team] = {}
        self._roster_locked: bool = False
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

        self._roster_locked = bool(payload.get("roster_locked", False))
        self._teams = {team_dict["name"].lower(): Team.from_dict(team_dict) for team_dict in payload.get("teams", [])}

    def _write(self) -> None:
        payload = {
            "teams": [team.to_dict() for team in self._teams.values()],
            "roster_locked": self._roster_locked,
        }
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def save(self) -> None:
        self._write()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def all_teams(self) -> Iterable[Team]:
        return list(self._teams.values())

    def get_team(self, name: str) -> Optional[Team]:
        return self._teams.get(name.lower())

    def get_team_by_role(self, role_id: int) -> Optional[Team]:
        for team in self._teams.values():
            if team.role_id == role_id:
                return team
        return None

    def find_team_for_member(self, member_id: int) -> Optional[Team]:
        for team in self._teams.values():
            if member_id == team.captain_id or member_id in team.co_captains or member_id in team.members:
                return team
        return None

    def invites_for_user(self, user_id: int) -> List[Team]:
        return [team for team in self._teams.values() if user_id in team.invites]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def create_team(
        self,
        *,
        name: str,
        hex_color: str,
        role_id: int,
        captain_id: int,
        icon_url: Optional[str] = None,
    ) -> Team:
        key = name.lower()
        if key in self._teams:
            raise ValueError("A team with that name already exists")

        team = Team(
            name=name,
            hex_color=hex_color,
            role_id=role_id,
            captain_id=captain_id,
            icon_url=icon_url,
            co_captains=[],
            members=[captain_id],
            invites=[],
        )
        self._teams[key] = team
        self.save()
        return team

    def update_team(self, team: Team) -> None:
        self._teams[team.name.lower()] = team
        self.save()

    def delete_team(self, name: str) -> None:
        key = name.lower()
        if key in self._teams:
            del self._teams[key]
            self.save()

    def add_member(self, team: Team, member_id: int) -> None:
        if member_id not in team.members:
            team.members.append(member_id)
        if member_id in team.invites:
            team.invites.remove(member_id)
        self.update_team(team)

    def remove_member(self, team: Team, member_id: int) -> None:
        if member_id == team.captain_id:
            raise ValueError("Cannot remove the captain without transferring ownership")
        if member_id in team.members:
            team.members.remove(member_id)
        if member_id in team.co_captains:
            team.co_captains.remove(member_id)
        self.update_team(team)

    def set_captain(self, team: Team, member_id: int) -> None:
        if member_id not in team.members:
            team.members.append(member_id)
        if member_id in team.co_captains:
            team.co_captains.remove(member_id)
        team.captain_id = member_id
        self.update_team(team)

    def toggle_co_captain(self, team: Team, member_id: int) -> bool:
        if member_id in team.co_captains:
            team.co_captains.remove(member_id)
            result = False
        else:
            if member_id not in team.members:
                team.members.append(member_id)
            team.co_captains.append(member_id)
            result = True
        self.update_team(team)
        return result

    def add_invite(self, team: Team, user_id: int) -> None:
        if user_id not in team.invites:
            team.invites.append(user_id)
            self.update_team(team)

    def remove_invite(self, team: Team, user_id: int) -> None:
        if user_id in team.invites:
            team.invites.remove(user_id)
            self.update_team(team)

    def clear_invites_for_user(self, user_id: int) -> None:
        changed = False
        for team in self._teams.values():
            if user_id in team.invites:
                team.invites.remove(user_id)
                changed = True
        if changed:
            self.save()

    def set_hex(self, team: Team, hex_color: str) -> None:
        team.hex_color = hex_color
        self.update_team(team)

    def set_icon_url(self, team: Team, icon_url: Optional[str]) -> None:
        team.icon_url = icon_url
        self.update_team(team)

    def rename(self, team: Team, new_name: str) -> None:
        del self._teams[team.name.lower()]
        team.name = new_name
        self._teams[new_name.lower()] = team
        self.save()

    # ------------------------------------------------------------------
    # Roster lock management
    # ------------------------------------------------------------------
    @property
    def roster_locked(self) -> bool:
        return self._roster_locked

    def set_roster_locked(self, locked: bool) -> None:
        self._roster_locked = locked
        self.save()
