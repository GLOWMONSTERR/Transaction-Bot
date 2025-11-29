"""Entry point for the Discord league management bot."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from aiohttp import web

from .config import BotConfig
from .match_manager import MatchManager
from .team_manager import Team, TeamManager
from .views import (
    ConfirmView,
    ManageTeamView,
    RosterLookupView,
    _safe_delete_role,
    _safe_remove_role,
    build_team_embed,
    prompt_confirmation,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LeagueBot(commands.Bot):
    """Custom bot implementation that wires together commands and persistence."""

    def __init__(self, *, config: BotConfig, data_path: Path, match_path: Path) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.config = config
        self.team_manager = TeamManager(data_path)
        self.match_manager = MatchManager(match_path)
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
        self._reminder_loop.start()

    def cog_unload(self) -> None:
        self._reminder_loop.cancel()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _send_ephemeral(self, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> None:
        """Reply to an interaction without risking double acknowledgements."""

        kwargs.setdefault("ephemeral", True)
        if interaction.response.is_done():
            await interaction.followup.send(*args, **kwargs)
        else:
            await interaction.response.send_message(*args, **kwargs)

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

    def _match_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        if not self.bot.config.match_category_id:
            return None
        channel = guild.get_channel(self.bot.config.match_category_id)
        return channel if isinstance(channel, discord.CategoryChannel) else None

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

    async def _post_results(
        self,
        guild: discord.Guild,
        *,
        winner: str,
        loser: str,
        rounds: List[str],
    ) -> None:
        channel_id = self.bot.config.match_results_channel_id
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                fetched = await guild.fetch_channel(channel_id)
            except (discord.Forbidden, discord.HTTPException):
                return
            if not isinstance(fetched, discord.TextChannel):
                return
            channel = fetched

        lines = [f"**{winner}** has beaten **{loser}**"]
        for idx in range(5):
            label = f"R{idx + 1}:"
            value = rounds[idx] if idx < len(rounds) else ""
            lines.append(f"{label} {value}".rstrip())

        try:
            await channel.send("\n".join(lines))
        except discord.HTTPException:
            return

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
            await self._send_ephemeral(interaction, "Only administrators can create teams.")
            return

        hex_code = hex_code.strip().lstrip("#")
        if len(hex_code) not in {6, 8}:
            await self._send_ephemeral(interaction, "Hex codes must be 6 or 8 characters.")
            return

        guild = interaction.guild
        if guild is None:
            await self._send_ephemeral(interaction, "This command can only be used inside a server.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

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
            await self._send_ephemeral(interaction, str(exc))
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
        await self._send_ephemeral(interaction, message)
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
            await self._send_ephemeral(interaction, "You are not a member of any team.")
            return

        is_captain = interaction.user.id == team.captain_id
        is_co_captain = interaction.user.id in team.co_captains
        is_admin = self._require_admin(interaction)
        if not (is_captain or is_co_captain or is_admin):
            await self._send_ephemeral(interaction, "You are not authorised to manage this team.")
            return

        roster_locked = self.bot.team_manager.roster_locked
        view = ManageTeamView(
            interaction=interaction,
            team=team,
            manager=self.bot.team_manager,
            bot=self.bot,
            is_admin=is_admin,
            roster_locked=roster_locked,
            can_invite=not roster_locked,
            allow_force_add=False,
            captain_role=self._get_role(interaction.guild, self.bot.config.captain_role_id),
            co_captain_role=self._get_role(interaction.guild, self.bot.config.co_captain_role_id),
            member_role=self._get_role(interaction.guild, self.bot.config.team_member_role_id),
        )
        await self._send_ephemeral(
            interaction,
            embed=build_team_embed(team, interaction.guild),
            view=view,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="roster", description="Browse rosters for any team")
    async def roster(self, interaction: discord.Interaction) -> None:
        teams = sorted(self.bot.team_manager.all_teams(), key=lambda team: team.name.lower())
        if not teams:
            await self._send_ephemeral(interaction, "No teams have been created yet.")
            return

        view = RosterLookupView(interaction=interaction, teams=teams)
        await self._send_ephemeral(
            interaction,
            embed=build_team_embed(view.current_team, interaction.guild),
            view=view,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="leave", description="Leave your current team")
    async def leave_team(self, interaction: discord.Interaction) -> None:
        team = self.bot.team_manager.find_team_for_member(interaction.user.id)
        if not team:
            await self._send_ephemeral(interaction, "You are not on a roster.")
            return
        if interaction.user.id == team.captain_id:
            await self._send_ephemeral(interaction, "Captains must transfer or disband their team first.")
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

    def _week_window(self, now: Optional[datetime] = None) -> tuple[datetime, datetime, datetime, int]:
        """Return (start_of_week, due_at, reminder_at, week_number)."""

        now = now or datetime.utcnow()
        start = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time())
        due = start + timedelta(days=7)
        reminder = start + timedelta(days=3, hours=12)
        week_number = int(((start - datetime(start.year, 1, 1)).days // 7) + 1)
        return start, due, reminder, week_number

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
            await self._send_ephemeral(interaction, "Administrator permissions are required.")
            return

        team = self.bot.team_manager.get_team(team_name)
        if not team:
            await self._send_ephemeral(interaction, "Team not found.")
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
            try:
                self.bot.team_manager.set_captain(team, new_captain.id)
            except ValueError as exc:
                await self._send_ephemeral(interaction, str(exc))
                return
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

        await self._send_ephemeral(interaction, "Team updated successfully.")

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-create-match", description="Admin: create a weekly match channel for two teams")
    @app_commands.autocomplete(team_one=_team_autocomplete, team_two=_team_autocomplete)
    @app_commands.describe(
        team_one="Home team",
        team_two="Away team",
        week="Week number (defaults to current week)",
    )
    async def admin_create_match(
        self,
        interaction: discord.Interaction,
        team_one: str,
        team_two: str,
        week: Optional[int] = None,
    ) -> None:
        if not self._require_admin(interaction):
            await self._send_ephemeral(interaction, "Administrator permissions are required.")
            return

        guild = interaction.guild
        if guild is None:
            await self._send_ephemeral(interaction, "This command can only be used inside a server.")
            return

        if team_one.lower() == team_two.lower():
            await self._send_ephemeral(interaction, "Pick two different teams for a match.")
            return

        category = self._match_category(guild)
        if not category:
            await self._send_ephemeral(interaction, "Set MATCH_CATEGORY_ID to a valid category before making matches.")
            return

        team_one_obj = self.bot.team_manager.get_team(team_one)
        team_two_obj = self.bot.team_manager.get_team(team_two)
        if not team_one_obj or not team_two_obj:
            await self._send_ephemeral(interaction, "Both teams must exist before scheduling a match.")
            return

        _, due_at, _, default_week = self._week_window()
        week_number = week or default_week

        channel_name = f"{team_one_obj.name.lower().replace(' ', '-')}-vs-{team_two_obj.name.lower().replace(' ', '-')}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for team in (team_one_obj, team_two_obj):
            role = guild.get_role(team.role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason="New league match",
            topic=f"Week {week_number} match due by {due_at.date().isoformat()}",
        )

        match = self.bot.match_manager.create_match(
            team_one=team_one_obj.name,
            team_two=team_two_obj.name,
            channel_id=channel.id,
            due_at=due_at,
            week=week_number,
        )

        from .views import MatchControlView  # local import to avoid cycles

        view = MatchControlView(
            match=match,
            manager=self.bot.match_manager,
            team_manager=self.bot.team_manager,
            bot=self.bot,
            post_results=self._post_results,
        )

        due_ts = int(due_at.timestamp())
        staff_pings = []
        for role_id in (self.bot.config.caster_role_id, self.bot.config.ref_role_id, self.bot.config.mod_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role:
                staff_pings.append(role.mention)
        staff_line = f" {' '.join(staff_pings)}" if staff_pings else ""

        await channel.send(
            content=(
                f"Week {week_number} match created for **{team_one_obj.name}** vs **{team_two_obj.name}**.\n"
                f"Matches run Monday to Monday. Due by <t:{due_ts}:F>. Mid-week reminders go out automatically.{staff_line}"
            ),
            view=view,
        )
        await self._send_ephemeral(interaction, f"Match channel created: {channel.mention}")

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-manage", description="Admin: manage any team")
    @app_commands.autocomplete(team_name=_team_autocomplete)
    async def admin_manage(self, interaction: discord.Interaction, team_name: str) -> None:
        if not self._require_admin(interaction):
            await self._send_ephemeral(interaction, "Administrator permissions are required.")
            return

        team = self.bot.team_manager.get_team(team_name)
        if not team:
            await self._send_ephemeral(interaction, "Team not found.")
            return

        view = ManageTeamView(
            interaction=interaction,
            team=team,
            manager=self.bot.team_manager,
            bot=self.bot,
            is_admin=True,
            roster_locked=self.bot.team_manager.roster_locked,
            can_invite=True,
            allow_force_add=True,
            captain_role=self._get_role(interaction.guild, self.bot.config.captain_role_id),
            co_captain_role=self._get_role(interaction.guild, self.bot.config.co_captain_role_id),
            member_role=self._get_role(interaction.guild, self.bot.config.team_member_role_id),
        )
        await self._send_ephemeral(
            interaction,
            embed=build_team_embed(team, interaction.guild),
            view=view,
        )

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-lock", description="Admin: toggle roster lock")
    async def admin_lock(self, interaction: discord.Interaction) -> None:
        if not self._require_admin(interaction):
            await self._send_ephemeral(interaction, "Administrator permissions are required.")
            return

        locked = not self.bot.team_manager.roster_locked
        self.bot.team_manager.set_roster_locked(locked)
        state = "locked" if locked else "unlocked"
        await self._send_ephemeral(interaction, f"Rosters are now {state}.")

    # ------------------------------------------------------------------
    @app_commands.command(name="admin-disband-all", description="Admin: disband every team")
    async def admin_disband_all(self, interaction: discord.Interaction) -> None:
        if not self._require_admin(interaction):
            await self._send_ephemeral(interaction, "Administrator permissions are required.")
            return

        teams = list(self.bot.team_manager.all_teams())
        if not teams:
            await self._send_ephemeral(interaction, "There are no teams to disband.")
            return

        confirm_one = ConfirmView()
        await self._send_ephemeral(
            interaction,
            "This will delete every team, role, and roster entry. Confirm (1/3).",
            view=confirm_one,
        )
        await confirm_one.wait()
        if confirm_one.value is not True:
            return

        confirm_two = ConfirmView()
        await interaction.followup.send(
            "Second confirmation required (2/3).",
            view=confirm_two,
            ephemeral=True,
        )
        await confirm_two.wait()
        if confirm_two.value is not True:
            return

        confirm_three = ConfirmView()
        await interaction.followup.send(
            "Final confirmation (3/3). This cannot be undone.",
            view=confirm_three,
            ephemeral=True,
        )
        await confirm_three.wait()
        if confirm_three.value is not True:
            return

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send(
                "This command can only be used inside a server.", ephemeral=True
            )
            return

        captain_role = self._get_role(guild, self.bot.config.captain_role_id)
        co_captain_role = self._get_role(guild, self.bot.config.co_captain_role_id)
        member_role = self._get_role(guild, self.bot.config.team_member_role_id)

        disbanded = 0
        notes: List[str] = []

        for team in teams:
            disbanded += 1
            team_role = guild.get_role(team.role_id)

            message = await _safe_delete_role(team_role, reason="All teams disbanded by admin")
            if message:
                notes.append(f"{team.name}: {message}")

            member_ids = set(team.members)
            member_ids.add(team.captain_id)
            member_ids.update(team.co_captains)

            for member_id in member_ids:
                member = guild.get_member(member_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(member_id)
                    except discord.HTTPException:
                        member = None
                if member is None:
                    continue

                message = await _safe_remove_role(
                    member, team_role, reason="All teams disbanded by admin"
                )
                if message:
                    notes.append(f"{team.name}: {message}")

                if member_id == team.captain_id:
                    message = await _safe_remove_role(
                        member, captain_role, reason="All teams disbanded by admin"
                    )
                    if message:
                        notes.append(f"{team.name}: {message}")

                if member_id in team.co_captains:
                    message = await _safe_remove_role(
                        member, co_captain_role, reason="All teams disbanded by admin"
                    )
                    if message:
                        notes.append(f"{team.name}: {message}")

                message = await _safe_remove_role(
                    member, member_role, reason="All teams disbanded by admin"
                )
                if message:
                    notes.append(f"{team.name}: {message}")

            await self.bot.log_event(guild, f"## Team {team.name} has been disbanded")
            self.bot.team_manager.delete_team(team.name)

        summary = f"Disbanded {disbanded} team(s)."
        if notes:
            unique_notes = list(dict.fromkeys(notes))
            summary = "\n".join([summary, *unique_notes])

        await interaction.followup.send(summary, ephemeral=True)

    # ------------------------------------------------------------------
    @tasks.loop(minutes=30)
    async def _reminder_loop(self) -> None:
        await self.bot.wait_until_ready()
        now = datetime.utcnow()

        for match in self.bot.match_manager.open_matches():
            due_at = match.due_datetime()
            reminder_at = due_at - timedelta(days=3, hours=12)

            channel = self.bot.get_channel(match.channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue

            guild = channel.guild
            team_one = self.bot.team_manager.get_team(match.team_one)
            team_two = self.bot.team_manager.get_team(match.team_two)
            team_one_ping = guild.get_role(team_one.role_id).mention if team_one and guild.get_role(team_one.role_id) else match.team_one
            team_two_ping = guild.get_role(team_two.role_id).mention if team_two and guild.get_role(team_two.role_id) else match.team_two

            if not match.reminder_sent and now >= reminder_at and now < due_at:
                await channel.send(
                    f"Mid-week reminder: {team_one_ping} vs {team_two_ping} is due by <t:{int(due_at.timestamp())}:F>."
                )
                self.bot.match_manager.mark_reminded(match)

            if now >= due_at:
                self.bot.match_manager.mark_overdue(match)
                new_name = channel.name
                if not channel.name.startswith("⚠️"):
                    new_name = f"⚠️{channel.name}"
                    try:
                        await channel.edit(name=new_name)
                    except discord.HTTPException:
                        pass

                mod_ping = None
                if self.bot.config.mod_role_id:
                    role = guild.get_role(self.bot.config.mod_role_id)
                    if role:
                        mod_ping = role.mention
                ping = f" {mod_ping}" if mod_ping else ""
                await channel.send(
                    f"No score was reported before the weekly deadline. {team_one_ping} vs {team_two_ping}{ping}"
                )


def run_bot() -> None:
    """Load configuration and start the Discord bot."""

    config = BotConfig.from_env()
    data_path = Path("data/teams.json")
    match_path = Path("data/matches.json")
    bot = LeagueBot(config=config, data_path=data_path, match_path=match_path)
    bot.run(config.token)


if __name__ == "__main__":
    run_bot()
