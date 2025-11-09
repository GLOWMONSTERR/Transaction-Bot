# League Management Discord Bot

A Discord bot built with [`discord.py`](https://discordpy.readthedocs.io/en/stable/) that manages competitive teams inside a server. Administrators can create teams, captains can manage rosters, and players can accept invites — all powered by slash commands and persistent JSON storage.

## Features

- `/create-team` automatically creates a coloured role, assigns a captain, and stores metadata in `data/teams.json`.
- `/manage-team` gives captains and co-captains a management dashboard with invite, kick, promote, disband, and transfer controls.
- `/check-invites` shows an interactive carousel of pending invites for any player.
- `/leave` lets non-captain members leave their team after confirmation.
- `/admin-edit`, `/admin-manage`, and `/admin-lock` offer complete administrative control, including roster locks and manual overrides.

## Project layout

```
├── bot/
│   ├── __init__.py
│   ├── bot.py          # Bot entry point and slash command definitions
│   ├── config.py       # Environment-variable driven configuration loader
│   ├── team_manager.py # JSON persistence for teams/invites
│   └── views.py        # Discord UI views (buttons, selects, embeds)
├── data/
│   └── teams.json      # Persisted team roster data
├── requirements.txt    # Python dependencies
└── .env.example        # Template for runtime configuration
```

## Prerequisites

- Python 3.10 or later (discord.py requires modern asyncio features).
- A Discord application with a bot token and the **Server Members Intent** enabled.
- (Recommended) [Visual Studio Code](https://code.visualstudio.com/) with the Python extension.

## Create a Discord bot that only you can invite

1. Visit the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Give the application a name, accept the terms, and create it. This also creates the default *General Information* page where you can upload an icon.
3. Open the **Bot** tab on the left and click **Add Bot** to turn the application into a bot user.
4. Under the **Privileged Gateway Intents** section, enable **Server Members Intent** (and any other intents you plan to use).
5. In the **Authorization Flow** section, make sure **Public Bot** is toggled **off**. This prevents anyone else from inviting the bot to their server.
6. (Optional) Toggle **Requires OAuth2 Code Grant** off unless you are building a full OAuth flow.
7. Scroll to the **Token** section, click **Reset Token**, and copy the generated token. Paste it into your `.env` file as `DISCORD_TOKEN`.
8. Finally, use the **OAuth2 > URL Generator** tab to create your personal invite link with the `applications.commands` and `bot` scopes. Because the bot is not public, only you (and any users you explicitly add as Team Members in the Developer Portal) will be able to invite it with this link.

## Running the bot in Visual Studio Code

1. **Clone the repository**
   - Open VS Code.
   - Use `View > Command Palette…` and run `Git: Clone`.
   - Paste the repository URL and choose a local folder. When prompted, open the cloned workspace.

2. **Create a virtual environment**
   - Open the integrated terminal (`Terminal > New Terminal`).
   - Create the environment:
     - **macOS/Linux**: `python3 -m venv .venv`
     - **Windows**: `py -3 -m venv .venv`
   - Activate it:
     - **macOS/Linux**: `source .venv/bin/activate`
     - **Windows PowerShell**: `.venv\Scripts\Activate.ps1`

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Duplicate `.env.example` to `.env`.
   - Fill in:
     - `DISCORD_TOKEN`: your bot token.
     - `GUILD_ID` (optional): locks slash command sync to a single guild for faster updates while developing.
     - `CAPTAIN_ROLE_ID` and `CO_CAPTAIN_ROLE_ID` (optional): role IDs used for global captain/co-captain titles.

5. **Select the Python interpreter**
   - In VS Code, click the interpreter selector in the status bar and choose the interpreter from the `.venv` folder.

6. **Run the bot**
   - Press `F5` or use `Run > Start Debugging`.
   - Choose “Python File” if prompted.
   - Alternatively, run the entry point manually from the terminal:
     ```bash
     python -m bot.bot
     ```

7. **Invite the bot to your server**
   - Use the OAuth2 URL from the Discord Developer Portal with the `applications.commands` and `bot` scopes.
   - Grant permissions to manage roles and view members.

When the bot starts, it will sync slash commands (instantly if `GUILD_ID` is set). All team and invite data persists automatically in `data/teams.json`.

## Command summary

| Command | Who can use it | Description |
| --- | --- | --- |
| `/create-team <team_name> <hex_code> <profile_picture> <team_captain>` | Admins | Creates a new team, role, and assigns the captain. |
| `/manage-team` | Captains & co-captains | Interactive roster dashboard with invite, kick, promote, disband, and transfer options. |
| `/check-invites` | Everyone | Browse, accept, or decline outstanding team invites. |
| `/leave` | Team members | Leave your current team (captains must transfer or disband first). |
| `/admin-edit` | Admins | Update team name, colour, logo, or captain. |
| `/admin-manage` | Admins | Access the management dashboard for any team. |
| `/admin-lock` | Admins | Toggle roster locks to prevent new invites. |

## Data storage

The bot persists its state in `data/teams.json`. You can back up or edit this file while the bot is offline. The structure includes the roster lock flag, teams, member IDs, and pending invites.

## Contributing

Pull requests are welcome! Please format code with the default `black` settings and ensure new features include documentation updates in this README.
