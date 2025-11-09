"""Entry point for the Discord league management bot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .config import BotConfig
from .team_manager import TeamManager
from .views import (
    InviteNavigationView,
    ManageTeamView,
    RosterLookupView,
    build_team_embed,
    prompt_confirmation,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LeagueBot(commands.Bot):
    """Custom bot implementation that wires together commands and persistence."""

    def __init__(self, *, config: BotConfig, data_path: Path) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.team_manager = TeamManager(data_path)

    async def setup_hook(self) -> None:
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", self.config.guild_id)
        else:
            await self.tree.sync()
            log.info("Synced commands globally")

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_role(self, guild: discord.Guild, role_id: Optional[int]) -> Optional[discord.Role]:
        if not role_id:
            return None
        return guild.get_role(role_id)

    def _require_admin(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            return False
        return True

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------
    @app_commands.command(name="create-team", description="Create a new league team")
    @app_commands.describe(
        team_name="Name of the team",
        hex_code="Role colour in hex format (e.g. #ff8800)",
        profile_picture="Role icon to use",
        team_captain="Captain that will lead the team",
    )
    async def create_team(
        self,
        interaction: discord.Interaction,
        team_name: str,
        hex_code: str,
        profile_picture: Optional[discord.Attachment],
        team_captain: discord.Member,
    ) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can create teams.", ephemeral=True)
            return

        hex_code = hex_code.strip().lstrip("#")
        if len(hex_code) not in {6, 8}:
            await interaction.response.send_message("Hex codes must be 6 or 8 characters.", ephemeral=True)
            return

        guild = interaction.guild
        colour = discord.Colour(int(hex_code, 16))
        role = await guild.create_role(name=team_name, colour=colour, reason="New league team")
        member_role = self._get_role(guild, self.config.team_member_role_id)

        icon_url = None
        if profile_picture:
            icon_bytes = await profile_picture.read()
            await role.edit(display_icon=icon_bytes)
            icon_url = profile_picture.url

        try:
            team = self.team_manager.create_team(
                name=team_name,
                hex_color=f"#{hex_code}",
                role_id=role.id,
                captain_id=team_captain.id,
                icon_url=icon_url,
            )
        except ValueError as exc:
            await role.delete(reason="Rolling back team creation")
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await team_captain.add_roles(role, reason="Team captain assigned")
        captain_role = self._get_role(guild, self.config.captain_role_id)
        if captain_role:
            await team_captain.add_roles(captain_role, reason="Granted global captain role")
        if member_role:
            await team_captain.add_roles(member_role, reason="Joined team roster")

        await interaction.response.send_message(f"Team {team.name} created successfully!", ephemeral=True)

    # ------------------------------------------------------------------
    @app_commands.command(name="manage-team", description="Manage your team roster")
    async def manage_team(self, interaction: discord.Interaction) -> None:
        team = self.team_manager.find_team_for_member(interaction.user.id)
        if not team:
            await interaction.response.send_message("You are not a member of any team.", ephemeral=True)
            return

        is_captain = interaction.user.id == team.captain_id
        is_co_captain = interaction.user.id in team.co_captains
        if not (is_captain or is_co_captain or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("You are not authorised to manage this team.", ephemeral=True)
            return

        view = ManageTeamView(
            interaction=interaction,
            team=team,
            manager=self.team_manager,
            is_admin=interaction.user.guild_permissions.administrator,
            roster_locked=self.team_manager.roster_locked,
            captain_role=self._get_role(interaction.guild, self.config.captain_role_id),
            co_captain_role=self._get_role(interaction.guild, self.config.co_captain_role_id),
            member_role=self._get_role(interaction.guild, self.config.team_member_role_id),
        )
        await interaction.response.send_message(embed=build_team_embed(team, interaction.guild), view=view, ephemeral=True)

    # ------------------------------------------------------------------
    @app_commands.command(name="check-invites", description="View your pending team invites")
    async def check_invites(self, interaction: discord.Interaction) -> None:
        invites = self.team_manager.invites_for_user(interaction.user.id)
        if not invites:
            await interaction.response.send_message("You have no pending invites.", ephemeral=True)
            return

        view = InviteNavigationView(
            interaction=interaction,
            teams=invites,
            manager=self.team_manager,
            member_role=self._get_role(interaction.guild, self.config.team_member_role_id),
        )
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

    # ------------------------------------------------------------------
    @app_commands.command(name="roster", description="Browse rosters for any team")
    async def roster(self, interaction: discord.Interaction) -> None:
        teams = sorted(self.team_manager.all_teams(), key=lambda team: team.name.lower())
        if not teams:
            await interaction.response.send_message("No teams have been created yet.", ephemeral=True)
            return

        view = RosterLookupView(interaction=interaction, teams=teams)
        await interaction.response.send_message(
            embed=build_team_embed(view.current_team, interaction.guild),
            view=view,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="leave", description="Leave your current team")
    async def leave_team(self, interaction: discord.Interaction) -> None:
        team = self.team_manager.find_team_for_member(interaction.user.id)
        if not team:
            await interaction.response.send_message("You are not on a roster.", ephemeral=True)
            return
        if interaction.user.id == team.captain_id:
            await interaction.response.send_message("Captains must transfer or disband their team first.", ephemeral=True)
            return

        confirmed = await prompt_confirmation(interaction, f"Leave {team.name}? This will remove your team role.")
        if not confirmed:
            return

        self.team_manager.remove_member(team, interaction.user.id)
        role = interaction.guild.get_role(team.role_id)
        if role:
            await interaction.user.remove_roles(role, reason="Left team")
        co_captain_role = self._get_role(interaction.guild, self.config.co_captain_role_id)
        if co_captain_role:
            await interaction.user.remove_roles(co_captain_role, reason="Left team")
        member_role = self._get_role(interaction.guild, self.config.team_member_role_id)
        if member_role:
            await interaction.user.remove_roles(member_role, reason="Left team")
        await interaction.followup.send(f"You have left {team.name}.", ephemeral=True)

    # ------------------------------------------------------------------
    async def _team_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        for team in self.team_manager.all_teams():
            if current.lower() in team.name.lower():
                choices.append(app_commands.Choice(name=team.name, value=team.name))
        return choices[:25]

    @app_commands.command(name="admin-edit", description="Admin: edit a team's settings")
    @app_commands.describe(
        team_name="Team to edit",
        new_name="New team name",
        new_hex="Updated hex colour (e.g. #00ff00)",
        new_logo="Upload a new role icon",
        new_captain="Transfer captaincy",
    )
    @app_commands.autocomplete(team_name=_team_autocomplete)
    async def admin_edit(
        self,
        interaction: discord.Interaction,
        team_name: str,
        new_name: Optional[str] = None,
        new_hex: Optional[str] = None,
        new_logo: Optional[discord.Attachment] = None,
        new_captain: Optional[discord.Member] = None,
    ) -> None:
        if not self._require_admin(interaction):
            await interaction.response.send_message("Administrator permissions are required.", ephemeral=True)
            return

        team = self.team_manager.get_team(team_name)
        if not team:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        role = interaction.guild.get_role(team.role_id)
        if new_name:
            if role:
                await role.edit(name=new_name)
            self.team_manager.rename(team, new_name)
        if new_hex:
            hex_value = new_hex.strip().lstrip("#")
            colour = discord.Colour(int(hex_value, 16))
            if role:
                await role.edit(colour=colour)
            self.team_manager.set_hex(team, f"#{hex_value}")
        if new_logo:
            icon_bytes = await new_logo.read()
            if role:
                await role.edit(display_icon=icon_bytes)
            self.team_manager.set_icon_url(team, new_logo.url)
        if new_captain:
            old_captain_id = team.captain_id
            self.team_manager.set_captain(team, new_captain.id)
            captain_role = self._get_role(interaction.guild, self.config.captain_role_id)
            member_role = self._get_role(interaction.guild, self.config.team_member_role_id)
            old_member = interaction.guild.get_member(old_captain_id)
            if old_member and captain_role:
                await old_member.remove_roles(captain_role, reason="Captaincy transferred")
            if captain_role:
                await new_captain.add_roles(captain_role, reason="Captaincy granted")
            if role:
                await new_captain.add_roles(role, reason="Captaincy granted")
            if member_role:
                await new_captain.add_roles(member_role, reason="Joined team roster")

        await interaction.response.send_message("Team updated successfully.", ephemeral=True)

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-manage", description="Admin: manage any team")
    @app_commands.autocomplete(team_name=_team_autocomplete)
    async def admin_manage(self, interaction: discord.Interaction, team_name: str) -> None:
        if not self._require_admin(interaction):
            await interaction.response.send_message("Administrator permissions are required.", ephemeral=True)
            return

        team = self.team_manager.get_team(team_name)
        if not team:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        view = ManageTeamView(
            interaction=interaction,
            team=team,
            manager=self.team_manager,
            is_admin=True,
            roster_locked=self.team_manager.roster_locked,
            captain_role=self._get_role(interaction.guild, self.config.captain_role_id),
            co_captain_role=self._get_role(interaction.guild, self.config.co_captain_role_id),
            member_role=self._get_role(interaction.guild, self.config.team_member_role_id),
        )
        await interaction.response.send_message(embed=build_team_embed(team, interaction.guild), view=view, ephemeral=True)

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-lock", description="Admin: toggle roster lock")
    async def admin_lock(self, interaction: discord.Interaction) -> None:
        if not self._require_admin(interaction):
            await interaction.response.send_message("Administrator permissions are required.", ephemeral=True)
            return

        locked = not self.team_manager.roster_locked
        self.team_manager.set_roster_locked(locked)
        state = "locked" if locked else "unlocked"
        await interaction.response.send_message(f"Rosters are now {state}.", ephemeral=True)


def run_bot() -> None:
    """Load configuration and start the Discord bot."""

    config = BotConfig.from_env()
    data_path = Path("data/teams.json")
    bot = LeagueBot(config=config, data_path=data_path)
    bot.run(config.token)


if __name__ == "__main__":
    run_bot()
