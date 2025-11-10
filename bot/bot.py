"""Entry point for the Discord league management bot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web

from .config import BotConfig
from .team_manager import Team, TeamManager
from .views import (
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
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.config = config
        self.team_manager = TeamManager(data_path)
        self._web_runner: Optional[web.AppRunner] = None
        self._web_site: Optional[web.TCPSite] = None

    async def setup_hook(self) -> None:
        await self.add_cog(LeagueCommands(self))

        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", self.config.guild_id)
        else:
            await self.tree.sync()
            log.info("Synced commands globally")

        await self._start_status_site()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)

    async def log_event(self, guild: discord.Guild, content: str) -> None:
        channel_id = self.config.transactions_channel_id
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning("Unable to fetch transactions channel %s: %s", channel_id, exc)
                return

        if isinstance(channel, discord.Thread):
            target = channel
        elif isinstance(channel, discord.TextChannel):
            target = channel
        else:
            log.warning("Configured transactions channel %s is not a text-capable channel", channel_id)
            return

        try:
            await target.send(content)
        except discord.HTTPException as exc:
            log.warning("Failed to post event log message: %s", exc)

    async def _start_status_site(self) -> None:
        """Spin up a tiny web server that exposes a ping endpoint."""

        host = self.config.web_host or "0.0.0.0"
        port = self.config.web_port or 8080

        async def handle_root(request: web.Request) -> web.Response:
            return web.json_response({"status": "ok", "bot": str(self.user) if self.user else None})

        async def handle_ping(request: web.Request) -> web.Response:
            return web.Response(text="pong", content_type="text/plain")

        app = web.Application()
        app.router.add_get("/", handle_root)
        app.router.add_get("/ping", handle_ping)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=host, port=port)
        await site.start()
        self._web_runner = runner
        self._web_site = site
        log.info("Started status site on http://%s:%s", host, port)

    async def close(self) -> None:
        if self._web_site is not None:
            await self._web_site.stop()
            self._web_site = None
        if self._web_runner is not None:
            await self._web_runner.cleanup()
            self._web_runner = None
        await super().close()


class LeagueCommands(commands.Cog):
    """Slash-command collection that powers the league management workflow."""

    def __init__(self, bot: LeagueBot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_role(self, guild: discord.Guild, role_id: Optional[int]) -> Optional[discord.Role]:
        if not role_id:
            return None
        return guild.get_role(role_id)

    def _team_icon_url(self, guild: discord.Guild, team: Team) -> Optional[str]:
        role = guild.get_role(team.role_id)
        if role and role.display_icon:
            return role.display_icon.url
        return team.icon_url

    def _team_colour(self, team: Team) -> discord.Colour:
        return discord.Colour(int(team.hex_color.lstrip("#"), 16))

    def _require_admin(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if isinstance(member, discord.Member):
            if member.guild_permissions.administrator:
                return True

            configured_roles = set(self.bot.config.admin_role_ids)
            if configured_roles:
                user_roles = {role.id for role in member.roles}
                if configured_roles.intersection(user_roles):
                    return True

        return False

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
        if not self._require_admin(interaction):
            await interaction.response.send_message("Only administrators can create teams.", ephemeral=True)
            return

        hex_code = hex_code.strip().lstrip("#")
        if len(hex_code) not in {6, 8}:
            await interaction.response.send_message("Hex codes must be 6 or 8 characters.", ephemeral=True)
            return

        guild = interaction.guild
        colour = discord.Colour(int(hex_code, 16))
        role = await guild.create_role(name=team_name, colour=colour, reason="New league team")
        member_role = self._get_role(guild, self.bot.config.team_member_role_id)

        icon_url = None
        creation_notes: List[str] = []
        if profile_picture:
            icon_url = profile_picture.url
            icon_bytes = await profile_picture.read()
            try:
                await role.edit(display_icon=icon_bytes)
            except discord.Forbidden:
                log.warning("Server does not support role icons; skipping team icon upload.")
                creation_notes.append(
                    "Team created, but the role icon could not be applied because this server needs to be Level 2 for role icons."
                )
            except discord.HTTPException as exc:
                log.warning("Failed to apply role icon: %s", exc)
                creation_notes.append("Team created, but the role icon could not be applied due to a Discord error.")

        try:
            team = self.bot.team_manager.create_team(
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

        async def grant_role(target_role: Optional[discord.Role], *, description: str, failure_label: str) -> None:
            if not target_role:
                return
            try:
                await team_captain.add_roles(target_role, reason=description)
            except discord.Forbidden:
                creation_notes.append(
                    f"Team created, but I couldn't assign the {failure_label}. Move my bot role above it and ensure I have the Manage Roles permission."
                )
            except discord.HTTPException:
                creation_notes.append(f"Team created, but assigning the {failure_label} failed due to a Discord error.")

        await grant_role(role, description="Team captain assigned", failure_label=f"team role ({role.name})")
        captain_role = self._get_role(guild, self.bot.config.captain_role_id)
        await grant_role(captain_role, description="Granted global captain role", failure_label="captain role")
        await grant_role(member_role, description="Joined team roster", failure_label="team member role")

        message = f"Team {team.name} created successfully!"
        if creation_notes:
            message = "\n".join([message, *creation_notes])
        await interaction.response.send_message(message, ephemeral=True)
        role_ping = role.mention if isinstance(role, discord.Role) else f"**{team.name}**"
        content = (
            "## New Team Created!\n\n"
            f"- Team Name: {role_ping}\n"
            f"- Team Captain: {team_captain.mention}"
        )
        await self.bot.log_event(guild, content)

    # ------------------------------------------------------------------
    @app_commands.command(name="manage-team", description="Manage your team roster")
    async def manage_team(self, interaction: discord.Interaction) -> None:
        team = self.bot.team_manager.find_team_for_member(interaction.user.id)
        if not team:
            await interaction.response.send_message("You are not a member of any team.", ephemeral=True)
            return

        is_captain = interaction.user.id == team.captain_id
        is_co_captain = interaction.user.id in team.co_captains
        is_admin = self._require_admin(interaction)
        if not (is_captain or is_co_captain or is_admin):
            await interaction.response.send_message("You are not authorised to manage this team.", ephemeral=True)
            return

        view = ManageTeamView(
            interaction=interaction,
            team=team,
            manager=self.bot.team_manager,
            bot=self.bot,
            is_admin=is_admin,
            roster_locked=self.bot.team_manager.roster_locked,
            captain_role=self._get_role(interaction.guild, self.bot.config.captain_role_id),
            co_captain_role=self._get_role(interaction.guild, self.bot.config.co_captain_role_id),
            member_role=self._get_role(interaction.guild, self.bot.config.team_member_role_id),
        )
        await interaction.response.send_message(
            embed=build_team_embed(team, interaction.guild),
            view=view,
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="roster", description="Browse rosters for any team")
    async def roster(self, interaction: discord.Interaction) -> None:
        teams = sorted(self.bot.team_manager.all_teams(), key=lambda team: team.name.lower())
        if not teams:
            await interaction.response.send_message("No teams have been created yet.", ephemeral=True)
            return

        view = RosterLookupView(interaction=interaction, teams=teams)
        await interaction.response.send_message(
            embed=build_team_embed(view.current_team, interaction.guild),
            view=view,
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="leave", description="Leave your current team")
    async def leave_team(self, interaction: discord.Interaction) -> None:
        team = self.bot.team_manager.find_team_for_member(interaction.user.id)
        if not team:
            await interaction.response.send_message("You are not on a roster.", ephemeral=True)
            return
        if interaction.user.id == team.captain_id:
            await interaction.response.send_message("Captains must transfer or disband their team first.", ephemeral=True)
            return

        confirmed = await prompt_confirmation(interaction, f"Leave {team.name}? This will remove your team role.")
        if not confirmed:
            return

        self.bot.team_manager.remove_member(team, interaction.user.id)
        notes: List[str] = []

        async def remove_role(target_role: Optional[discord.Role], *, label: str) -> None:
            if not target_role:
                return
            try:
                await interaction.user.remove_roles(target_role, reason="Left team")
            except discord.Forbidden:
                notes.append(
                    f"Left the team, but I couldn't remove the {label}. Check my role position and permissions."
                )
            except discord.HTTPException:
                notes.append(f"Left the team, but removing the {label} failed due to a Discord error.")

        await remove_role(interaction.guild.get_role(team.role_id), label="team role")
        await remove_role(
            self._get_role(interaction.guild, self.bot.config.co_captain_role_id), label="co-captain role"
        )
        await remove_role(
            self._get_role(interaction.guild, self.bot.config.team_member_role_id), label="team member role"
        )

        message = f"You have left {team.name}."
        if notes:
            message = "\n".join([message, *list(dict.fromkeys(notes))])
        await interaction.followup.send(message, ephemeral=True)
        await self.bot.log_event(
            interaction.guild,
            f"{interaction.user.mention} has left **{team.name}**",
        )

    # ------------------------------------------------------------------
    async def _team_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices: List[app_commands.Choice[str]] = []
        for team in self.bot.team_manager.all_teams():
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

        team = self.bot.team_manager.get_team(team_name)
        if not team:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        role = interaction.guild.get_role(team.role_id)
        if new_name:
            if role:
                await role.edit(name=new_name)
            self.bot.team_manager.rename(team, new_name)
        if new_hex:
            hex_value = new_hex.strip().lstrip("#")
            colour = discord.Colour(int(hex_value, 16))
            if role:
                await role.edit(colour=colour)
            self.bot.team_manager.set_hex(team, f"#{hex_value}")
        if new_logo:
            icon_bytes = await new_logo.read()
            if role:
                await role.edit(display_icon=icon_bytes)
            self.bot.team_manager.set_icon_url(team, new_logo.url)
        if new_captain:
            old_captain_id = team.captain_id
            self.bot.team_manager.set_captain(team, new_captain.id)
            captain_role = self._get_role(interaction.guild, self.bot.config.captain_role_id)
            member_role = self._get_role(interaction.guild, self.bot.config.team_member_role_id)
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

        team = self.bot.team_manager.get_team(team_name)
        if not team:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        view = ManageTeamView(
            interaction=interaction,
            team=team,
            manager=self.bot.team_manager,
            bot=self.bot,
            is_admin=True,
            roster_locked=self.bot.team_manager.roster_locked,
            captain_role=self._get_role(interaction.guild, self.bot.config.captain_role_id),
            co_captain_role=self._get_role(interaction.guild, self.bot.config.co_captain_role_id),
            member_role=self._get_role(interaction.guild, self.bot.config.team_member_role_id),
        )
        await interaction.response.send_message(
            embed=build_team_embed(team, interaction.guild),
            view=view,
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-lock", description="Admin: toggle roster lock")
    async def admin_lock(self, interaction: discord.Interaction) -> None:
        if not self._require_admin(interaction):
            await interaction.response.send_message("Administrator permissions are required.", ephemeral=True)
            return

        locked = not self.bot.team_manager.roster_locked
        self.bot.team_manager.set_roster_locked(locked)
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
