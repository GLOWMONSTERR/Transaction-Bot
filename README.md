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

The checklist below walks through everything from installing VS Code to seeing the bot online. If this is your first time using VS Code or Python, don’t worry—each step includes the exact buttons to click.

1. **Install the tools (one-time setup)**
   - [Download VS Code](https://code.visualstudio.com/) and install it.
   - Install [Python 3.10+](https://www.python.org/downloads/). During the Windows installer, check **“Add Python to PATH.”**
   - Launch VS Code when both installers finish and accept the prompt to install the **Python** extension if it appears.

2. **Get the project into VS Code**
   - In VS Code, press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS) to open the **Command Palette**.
   - Type “Git: Clone” and press **Enter**.
   - Paste the repository URL and choose a folder where the files should live. VS Code will ask whether you want to open the clone—click **Open**.
   - If you already downloaded a ZIP, choose **File > Open Folder…** instead and pick the unzipped folder.

3. **Create a Python virtual environment**
   - Open the integrated terminal with **Terminal > New Terminal**.
   - Run one of the commands below (pick the one for your platform) to create a `.venv` folder that keeps dependencies isolated:
     - **Windows**: `py -3 -m venv .venv`
     - **macOS/Linux**: `python3 -m venv .venv`
   - Activate the environment so VS Code uses it:
     - **Windows PowerShell**: `.venv\Scripts\Activate.ps1`
       - If PowerShell shows a *“running scripts is disabled on this system”* error, temporarily allow the activation script by running `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same PowerShell window, then repeat the activate command. The change only lasts for that one terminal session.
     - **Windows Command Prompt**: `.venv\Scripts\activate.bat`
     - **macOS/Linux**: `source .venv/bin/activate`
   - The terminal prompt should now start with `(.venv)`—that means you’re inside the virtual environment.

4. **Install Python packages**
   - With the virtual environment active, install the bot’s dependencies:
     ```bash
     pip install -r requirements.txt
     ```
     - If PowerShell reports that `pip` is not recognized, run `py -m pip install -r requirements.txt` instead. This uses the copy of `pip` bundled with Python even when the global `pip` command is unavailable.
   - VS Code might pop up a toast suggesting you select the interpreter from `.venv`. Click **Select** if you see it. If not, click the Python version shown in the status bar and choose the one inside `.venv` manually.

5. **Configure your `.env` file**
   - In the Explorer sidebar, right-click `.env.example` and choose **Copy** then **Paste**. Rename the copy to `.env`.
   - Open `.env` and fill in the values:
     - `DISCORD_TOKEN`: the bot token from the Developer Portal.
     - `GUILD_ID` (optional): a single server ID for faster command sync during development.
     - `CAPTAIN_ROLE_ID` / `CO_CAPTAIN_ROLE_ID` (optional): global role IDs if you use shared captain roles.
     - `TEAM_MEMBER_ROLE_ID` (optional): a general member role that everyone on a team should receive.

6. **Run and debug the bot**
   - Press **F5** or use **Run > Start Debugging**. When VS Code asks how to run it, pick **Python File**.
   - The terminal will show “Logged in as …” when the bot successfully connects. If you prefer running manually, use:
     ```bash
     python -m bot.bot
     ```

7. **Invite the bot to your server**
   - Use the private OAuth2 URL you generated earlier with the `applications.commands` and `bot` scopes.
   - Approve the permissions (role management and member viewing) so slash commands can function.

Once the bot is online, it will automatically register slash commands (instantly if `GUILD_ID` is set). Team and invite data are saved in `data/teams.json`, so you can stop and restart the bot without losing progress.

## Command summary

| Command | Who can use it | Description |
| --- | --- | --- |
| `/create-team <team_name> <hex_code> <profile_picture> <team_captain>` | Admins | Creates a new team, role, and assigns the captain. |
| `/manage-team` | Captains & co-captains | Interactive roster dashboard with invite, kick, promote, disband, and transfer options. |
| `/check-invites` | Everyone | Browse, accept, or decline outstanding team invites. |
| `/roster` | Everyone | View any team's roster with a searchable dropdown selector. |
| `/leave` | Team members | Leave your current team (captains must transfer or disband first). |
| `/admin-edit` | Admins | Update team name, colour, logo, or captain. |
| `/admin-manage` | Admins | Access the management dashboard for any team. |
| `/admin-lock` | Admins | Toggle roster locks to prevent new invites. |

## Data storage

The bot persists its state in `data/teams.json`. You can back up or edit this file while the bot is offline. The structure includes the roster lock flag, teams, member IDs, and pending invites.

## Contributing

Pull requests are welcome! Please format code with the default `black` settings and ensure new features include documentation updates in this README.
