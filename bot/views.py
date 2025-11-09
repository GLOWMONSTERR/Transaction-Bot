"""Discord UI components for managing teams."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Optional

import discord

from .team_manager import Team, TeamManager


def _hex_to_colour(hex_code: str) -> discord.Colour:
    hex_code = hex_code.lstrip("#")
    return discord.Colour(int(hex_code, 16))


def build_team_embed(team: Team, guild: discord.Guild) -> discord.Embed:
    role = guild.get_role(team.role_id)
    colour = _hex_to_colour(team.hex_color)
    embed = discord.Embed(title=f"{team.name} roster", colour=colour)
    if role and role.display_icon:
        embed.set_thumbnail(url=role.display_icon.url)
    elif team.icon_url:
        embed.set_thumbnail(url=team.icon_url)

    captain = guild.get_member(team.captain_id)
    captain_name = captain.display_name if captain else f"<@{team.captain_id}>"
    lines = [f"👑 {captain_name}"]

    for member_id in team.members:
        if member_id == team.captain_id:
            continue
        emoji = ""
        if member_id in team.co_captains:
            emoji = "👑👑 "
        member = guild.get_member(member_id)
        display_name = member.display_name if member else f"<@{member_id}>"
        lines.append(f"{emoji}{display_name}")

    if not lines:
        lines.append("No members yet")

    embed.add_field(name="Members", value="\n".join(lines), inline=False)
    if team.invites:
        invite_mentions = ", ".join(f"<@{user_id}>" for user_id in team.invites)
        embed.add_field(name="Pending invites", value=invite_mentions, inline=False)

    return embed


class ConfirmView(discord.ui.View):
    """Reusable confirmation dialog."""

    def __init__(self, *, timeout: Optional[float] = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.value = True
        self.stop()
        await interaction.response.edit_message(content="Action confirmed.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.value = False
        self.stop()
        await interaction.response.edit_message(content="Action cancelled.", view=None)


class InviteUserSelect(discord.ui.UserSelect):
    """User select menu for invites."""

    def __init__(self, callback: Callable[[discord.Interaction, discord.Member], Awaitable[None]]) -> None:
        super().__init__(placeholder="Select a player to invite", min_values=1, max_values=1)
        self._on_select = callback

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message("Member is not in this guild.", ephemeral=True)
            return
        await self._on_select(interaction, member)


class MemberSelect(discord.ui.Select):
    """Select component for choosing a team member."""

    def __init__(self, *, team: Team, guild: discord.Guild, on_select: Callable[[int], None]) -> None:
        options: List[discord.SelectOption] = []
        for member_id in team.members:
            member = guild.get_member(member_id)
            label = member.display_name if member else f"Member {member_id}"
            if member_id == team.captain_id:
                label = f"👑 {label}"
            elif member_id in team.co_captains:
                label = f"👑👑 {label}"
            options.append(discord.SelectOption(label=label, value=str(member_id)))
        super().__init__(placeholder="Select a member", options=options)
        self._on_select = on_select

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        member_id = int(self.values[0])
        self._on_select(member_id)
        await interaction.response.defer()


class ManageTeamView(discord.ui.View):
    """Interactive view used by captains and admins to manage a roster."""

    def __init__(
        self,
        *,
        interaction: discord.Interaction,
        team: Team,
        manager: TeamManager,
        is_admin: bool,
        roster_locked: bool,
        captain_role: Optional[discord.Role] = None,
        co_captain_role: Optional[discord.Role] = None,
        member_role: Optional[discord.Role] = None,
    ) -> None:
        super().__init__(timeout=300)
        self.interaction = interaction
        self.team = team
        self.manager = manager
        self.is_admin = is_admin
        self.roster_locked = roster_locked
        self.captain_role = captain_role
        self.co_captain_role = co_captain_role
        self.member_role = member_role
        self.selected_member: Optional[int] = None

        self.member_select = MemberSelect(team=team, guild=interaction.guild, on_select=self._select_member)
        if self.member_select.options:
            self.add_item(self.member_select)

        can_invite = not roster_locked or is_admin
        invite_style = discord.ButtonStyle.green if can_invite else discord.ButtonStyle.gray
        self.invite_button = discord.ui.Button(label="Invite", style=invite_style, disabled=not can_invite)
        self.invite_button.callback = self._on_invite  # type: ignore[assignment]
        self.add_item(self.invite_button)

        self.disband_button = discord.ui.Button(label="Disband", style=discord.ButtonStyle.danger)
        self.disband_button.callback = self._on_disband  # type: ignore[assignment]
        self.disband_button.disabled = not (is_admin or self.interaction.user.id == team.captain_id)
        self.add_item(self.disband_button)

        self.transfer_button = discord.ui.Button(label="Transfer captain", style=discord.ButtonStyle.blurple)
        self.transfer_button.callback = self._on_transfer  # type: ignore[assignment]
        self.transfer_button.disabled = not (is_admin or self.interaction.user.id == team.captain_id)
        self.add_item(self.transfer_button)

        self.kick_button = discord.ui.Button(label="Kick member", style=discord.ButtonStyle.danger, disabled=True)
        self.kick_button.callback = self._on_kick  # type: ignore[assignment]
        self.add_item(self.kick_button)

        self.promote_button = discord.ui.Button(label="Promote to co-captain", style=discord.ButtonStyle.primary, disabled=True)
        self.promote_button.callback = self._on_promote  # type: ignore[assignment]
        self.add_item(self.promote_button)

    # --------------------------------------------------------------
    # Member management helpers
    # --------------------------------------------------------------
    def _select_member(self, member_id: int) -> None:
        self.selected_member = member_id
        is_captain = member_id == self.team.captain_id
        is_co_captain = member_id in self.team.co_captains
        self.kick_button.disabled = is_captain and not self.is_admin
        if is_captain:
            self.promote_button.disabled = True
        else:
            self.promote_button.disabled = False
            if is_co_captain:
                self.promote_button.label = "Remove co-captain"
            else:
                self.promote_button.label = "Promote to co-captain"
        asyncio.create_task(self._refresh_message())

    async def _refresh_message(self) -> None:
        self._refresh_member_options()
        await self.interaction.edit_original_response(
            embed=build_team_embed(self.team, self.interaction.guild), view=self
        )

    def _refresh_member_options(self) -> None:
        if not hasattr(self, "member_select"):
            return
        options: List[discord.SelectOption] = []
        for member_id in self.team.members:
            member = self.interaction.guild.get_member(member_id)
            label = member.display_name if member else f"Member {member_id}"
            if member_id == self.team.captain_id:
                label = f"👑 {label}"
            elif member_id in self.team.co_captains:
                label = f"👑👑 {label}"
            options.append(discord.SelectOption(label=label, value=str(member_id)))
        if options:
            self.member_select.options = options
        else:
            if self.member_select in self.children:
                self.remove_item(self.member_select)

    async def _ensure_member(self, member_id: int) -> Optional[discord.Member]:
        member = self.interaction.guild.get_member(member_id)
        if not member:
            try:
                member = await self.interaction.guild.fetch_member(member_id)
            except discord.NotFound:
                return None
        return member

    async def _on_invite(self, interaction: discord.Interaction) -> None:
        if self.roster_locked and not self.is_admin:
            await interaction.response.send_message("Rosters are locked.", ephemeral=True)
            return

        view = discord.ui.View()

        async def handle_select(select_interaction: discord.Interaction, member: discord.Member) -> None:
            if member.id in self.team.members:
                await select_interaction.response.send_message("That player is already on your roster.", ephemeral=True)
                return
            if member.id in self.team.invites:
                await select_interaction.response.send_message("That player already has a pending invite.", ephemeral=True)
                return
            self.manager.add_invite(self.team, member.id)
            await select_interaction.response.send_message(f"Invited {member.mention} to {self.team.name}.", ephemeral=True)
            await self._refresh_message()

        view.add_item(InviteUserSelect(handle_select))
        await interaction.response.send_message("Search for a player to invite:", view=view, ephemeral=True)

    async def _on_disband(self, interaction: discord.Interaction) -> None:
        confirm = ConfirmView()
        await interaction.response.send_message(
            f"Are you sure you want to disband {self.team.name}? This cannot be undone.",
            view=confirm,
            ephemeral=True,
        )
        await confirm.wait()
        if confirm.value:
            guild = interaction.guild
            role = guild.get_role(self.team.role_id)
            if role:
                await role.delete(reason="Team disbanded")
            # Clean up extra roles
            if self.captain_role:
                captain_member = await self._ensure_member(self.team.captain_id)
                if captain_member:
                    await captain_member.remove_roles(self.captain_role, reason="Team disbanded")
            if self.co_captain_role:
                for member_id in list(self.team.co_captains):
                    member = await self._ensure_member(member_id)
                    if member:
                        await member.remove_roles(self.co_captain_role, reason="Team disbanded")
            if self.member_role:
                for member_id in list(self.team.members):
                    member = await self._ensure_member(member_id)
                    if member:
                        await member.remove_roles(self.member_role, reason="Team disbanded")
            self.manager.delete_team(self.team.name)
            await self.interaction.edit_original_response(content="Team disbanded.", embed=None, view=None)

    async def _on_transfer(self, interaction: discord.Interaction) -> None:
        options = []
        for member_id in self.team.members:
            if member_id == self.team.captain_id:
                continue
            member = interaction.guild.get_member(member_id)
            label = member.display_name if member else str(member_id)
            options.append(discord.SelectOption(label=label, value=str(member_id)))
        if not options:
            await interaction.response.send_message("No eligible members to transfer to.", ephemeral=True)
            return

        select = discord.ui.Select(placeholder="Select new captain", options=options)

        async def select_callback(select_interaction: discord.Interaction) -> None:
            new_captain_id = int(select.values[0])
            member = await self._ensure_member(new_captain_id)
            if not member:
                await select_interaction.response.send_message("Member is no longer in the guild.", ephemeral=True)
                return
            old_captain_id = self.team.captain_id
            self.manager.set_captain(self.team, new_captain_id)
            if self.captain_role:
                await member.add_roles(self.captain_role, reason="Promoted to captain")
            if self.captain_role and old_captain_id != new_captain_id:
                old_captain = await self._ensure_member(old_captain_id)
                if old_captain:
                    await old_captain.remove_roles(self.captain_role, reason="Captaincy transferred")
            if self.member_role:
                await member.add_roles(self.member_role, reason="Joined team roster")
            await select_interaction.response.send_message(f"Transferred captaincy to {member.mention}.", ephemeral=True)
            await self._refresh_message()

        select.callback = select_callback  # type: ignore[assignment]
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Choose the new captain:", view=view, ephemeral=True)

    async def _on_kick(self, interaction: discord.Interaction) -> None:
        if not self.selected_member:
            await interaction.response.send_message("Select a member first.", ephemeral=True)
            return
        was_co_captain = self.selected_member in self.team.co_captains
        try:
            self.manager.remove_member(self.team, self.selected_member)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        member = await self._ensure_member(self.selected_member)
        if member:
            role = interaction.guild.get_role(self.team.role_id)
            if role:
                await member.remove_roles(role, reason="Removed from team")
            if self.co_captain_role and was_co_captain:
                await member.remove_roles(self.co_captain_role, reason="Removed as co-captain")
            if self.member_role:
                await member.remove_roles(self.member_role, reason="Removed from team")
        await interaction.response.send_message("Member removed from the roster.", ephemeral=True)
        self.selected_member = None
        self.kick_button.disabled = True
        self.promote_button.disabled = True
        await self._refresh_message()

    async def _on_promote(self, interaction: discord.Interaction) -> None:
        if not self.selected_member:
            await interaction.response.send_message("Select a member first.", ephemeral=True)
            return
        was_promoted = self.manager.toggle_co_captain(self.team, self.selected_member)
        member = await self._ensure_member(self.selected_member)
        if member and self.co_captain_role:
            if was_promoted:
                await member.add_roles(self.co_captain_role, reason="Promoted to co-captain")
            else:
                await member.remove_roles(self.co_captain_role, reason="Demoted from co-captain")
        action = "Promoted" if was_promoted else "Removed co-captain"
        await interaction.response.send_message(f"{action} successfully.", ephemeral=True)
        await self._refresh_message()


class InviteNavigationView(discord.ui.View):
    """View that lets a user accept or decline team invites."""

    def __init__(
        self,
        *,
        interaction: discord.Interaction,
        teams: List[Team],
        manager: TeamManager,
        member_role: Optional[discord.Role] = None,
    ) -> None:
        super().__init__(timeout=300)
        self.interaction = interaction
        self.teams = teams
        self.manager = manager
        self.index = 0
        self.member_role = member_role

        self.prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self._prev  # type: ignore[assignment]
        self.add_item(self.prev_button)

        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.next_button.callback = self._next  # type: ignore[assignment]
        self.add_item(self.next_button)

        self.accept_button = discord.ui.Button(label="Accept", style=discord.ButtonStyle.success)
        self.accept_button.callback = self._accept  # type: ignore[assignment]
        self.add_item(self.accept_button)

        self.decline_button = discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger)
        self.decline_button.callback = self._decline  # type: ignore[assignment]
        self.add_item(self.decline_button)

        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index >= len(self.teams) - 1

    def current_team(self) -> Team:
        return self.teams[self.index]

    async def _prev(self, interaction: discord.Interaction) -> None:
        self.index = max(0, self.index - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.index = min(len(self.teams) - 1, self.index + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _accept(self, interaction: discord.Interaction) -> None:
        team = self.current_team()
        member = interaction.user
        role = interaction.guild.get_role(team.role_id)
        if role:
            await member.add_roles(role, reason="Accepted team invite")
        if self.member_role:
            await member.add_roles(self.member_role, reason="Joined team roster")
        self.manager.add_member(team, member.id)
        await interaction.response.send_message(f"You have joined {team.name}.", ephemeral=True)
        self.teams.remove(team)
        if not self.teams:
            await self.interaction.edit_original_response(content="You have no pending invites.", embed=None, view=None)
            return
        self.index = min(self.index, len(self.teams) - 1)
        self._update_buttons()
        await self.interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _decline(self, interaction: discord.Interaction) -> None:
        team = self.current_team()
        self.manager.remove_invite(team, interaction.user.id)
        await interaction.response.send_message(f"Declined invite to {team.name}.", ephemeral=True)
        self.teams.remove(team)
        if not self.teams:
            await self.interaction.edit_original_response(content="You have no pending invites.", embed=None, view=None)
            return
        self.index = min(self.index, len(self.teams) - 1)
        self._update_buttons()
        await self.interaction.edit_original_response(embed=self.build_embed(), view=self)

    def build_embed(self) -> discord.Embed:
        team = self.current_team()
        embed = build_team_embed(team, self.interaction.guild)
        embed.title = f"Invite {self.index + 1}/{len(self.teams)}: {team.name}"
        embed.description = "Use the buttons below to accept or decline the invite."
        return embed


async def prompt_confirmation(interaction: discord.Interaction, message: str) -> bool:
    view = ConfirmView()
    await interaction.response.send_message(message, view=view, ephemeral=True)
    await view.wait()
    return bool(view.value)


class RosterLookupView(discord.ui.View):
    """Public view that lets users browse team rosters via a dropdown."""

    def __init__(self, *, interaction: discord.Interaction, teams: List[Team]) -> None:
        super().__init__(timeout=180)
        if not teams:
            raise ValueError("RosterLookupView requires at least one team")

        self.interaction = interaction
        self._team_map = {team.name.lower(): team for team in teams}
        sorted_teams = sorted(teams, key=lambda team: team.name.lower())
        self.current_team = sorted_teams[0]

        options = []
        for team in sorted_teams[:25]:
            options.append(
                discord.SelectOption(
                    label=team.name,
                    value=team.name.lower(),
                    description=f"{len(team.members)} member(s)",
                )
            )

        self.team_select = discord.ui.Select(
            placeholder="Select a team to view",
            min_values=1,
            max_values=1,
            options=options,
        )
        if self.team_select.options:
            self.team_select.options[0].default = True
        self.team_select.callback = self._on_select  # type: ignore[assignment]
        self.add_item(self.team_select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        key = self.team_select.values[0]
        team = self._team_map.get(key)
        if not team:
            await interaction.response.send_message("That team could not be found.", ephemeral=True)
            return

        self.current_team = team
        guild = interaction.guild or self.interaction.guild
        await interaction.response.edit_message(
            embed=build_team_embed(team, guild),
            view=self,
        )

    async def on_timeout(self) -> None:
        self.team_select.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except discord.HTTPException:
            pass
