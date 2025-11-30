# League Management Discord Bot

A Discord bot built with [`discord.py`](https://discordpy.readthedocs.io/en/stable/) that manages competitive teams inside a server. Administrators can create teams, captains can manage rosters, and players can accept invites — all powered by slash commands and persistent JSON storage.

## Features

- `/create-team` automatically creates a coloured role, assigns a captain, and stores metadata in `data/teams.json`.
- `/manage-team` gives captains and co-captains a management dashboard with invite, kick, promote, disband, and transfer controls, sending direct-message invites that players can accept or decline instantly.
- Rosters are capped at five players (including the captain); invites, force-adds, and transfers respect the limit automatically.
- Optional transaction feed posts simple text updates whenever teams are created, captains change, players join/leave, or other roster actions occur.
- `/leave` lets non-captain members leave their team after confirmation.
- `/admin-edit`, `/admin-manage`, `/admin-lock`, and `/admin-disband-all` offer complete administrative control, including roster locks, forced additions, and mass disbands.
- `/admin-create-match` spins up weekly match channels inside a category you choose, pings both team roles, invites staff to self-assign (caster/ref/mod) via buttons, enforces a 7-day deadline, and locks channels + posts the result summary when scores are reported (first to 5, with round-by-round notes).
- `/submit-time` lets captains/co-captains post their agreed match time to a dedicated assignments channel so casters/refs/mods can claim the match and gain channel access when they accept.
- `/submit-scores` lets captains and co-captains report first-to-5 results with up to three attempts to agree; mismatches ping both teams (and mods on the last try), lock the channel on success, and optionally push the result to Challonge.
- `/admin-submit-scores` is an admin override to lock in a first-to-5 score directly from the match channel (useful for forfeits or disputes).

## Quick run-down (how the bot is used day to day)

1. **Stand up the bot** with your `.env` values (token, IDs, optional Challonge/staff settings) and launch it with `python -m bot.bot`. Commands sync automatically to your server.
2. **Create teams** using `/create-team` (admins only). The bot makes the coloured role, assigns the captain, saves the team to JSON, and posts a transaction feed entry if configured.
3. **Manage rosters** with `/manage-team` (captains/co-caps) or `/admin-manage` (admins). Invites are sent via DM; five-player cap enforcement applies everywhere, and roster locks disable captain invites while leaving admin tools available.
4. **Handle invites**: players accept/decline directly from their DMs. Captains can cancel outstanding invites from their dashboard; cancellations DM the recipient so nothing lingers silently.
5. **Run weekly matches** via `/admin-create-match`: the bot spins up `[team1]-vs-[team2]` channels in your match category, pings both team roles, and sets a 7-day deadline for score submission.
6. **Submit match time** with `/submit-time` from inside the match channel (captains/co-caps). The bot logs the time, posts a claim card to the assignments channel, and pings staff in the alert channel so casters/refs/mods can accept to get channel access for that specific match.
7. **Submit scores** with `/submit-scores` inside the match channel (captains/co-caps). Both sides must match within three attempts; success locks the channel, posts the plain-text result to the results channel, and updates Challonge when configured. If a forfeit or dispute needs an override, admins can use `/admin-submit-scores` to finalize the result instantly.
8. **Monitor activity** through the transaction feed (roster updates) and the match results channel. Deadline pings keep staff aware of overdue matches, and admin commands (`/admin-lock`, `/admin-disband-all`, `/admin-edit`) keep control centralized.

## Project layout

```
├── bot/
│   ├── __init__.py
│   ├── bot.py            # Bot entry point and slash command definitions
│   ├── config.py         # Environment-variable driven configuration loader
│   ├── team_manager.py   # JSON persistence for teams/invites
│   ├── match_manager.py  # JSON persistence for scheduled matches
│   └── views.py          # Discord UI views (buttons, selects, embeds)
├── data/
│   ├── teams.json        # Persisted team roster data
│   └── matches.json      # Persisted match schedule data
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
     - `TRANSACTIONS_CHANNEL_ID` (optional): a text channel ID where the bot will post roster changes, team creations, and other updates.
     - `ADMIN_ROLE_IDS` (optional): a comma-separated list (up to three) of role IDs (for example `123,456`) whose members should be treated as bot admins even if they don't have the Discord-wide Administrator permission.
     - `CASTER_ROLE_ID` / `REF_ROLE_ID` / `MOD_ROLE_ID` (optional): staff roles to ping and optionally grant when someone volunteers on a match channel.
     - `MATCH_CATEGORY_ID`: the category where weekly match channels will be created (required for `/admin-create-match`).
     - `MATCH_RESULTS_CHANNEL_ID` (optional): text channel where final results get posted in the requested format once scores are submitted.
     - `MATCH_ASSIGNMENTS_CHANNEL_ID` (optional): text channel where `/submit-time` posts claim cards so casters/refs/mods can accept a match and gain channel access.
    - `MATCH_STAFF_ALERT_CHANNEL_ID` (optional): a text channel where the bot will ping casters/refs/mods whenever teams submit their match time.
     - `WEB_HOST` / `WEB_PORT` (optional): override the mini status site's bind address (defaults to `0.0.0.0:8080`). Leave these blank to accept the defaults on free hosting providers.
     - `CHALLONGE_USERNAME` / `CHALLONGE_API_KEY` / `CHALLONGE_TOURNAMENT` (optional): fill these in to push final scores to your Challonge bracket (for example, the slug from https://challonge.com/y9wsh6ak).

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

## Weekly matches with `/admin-create-match`

- **Setup**: populate `MATCH_CATEGORY_ID` with the category you want match channels to live in. Point `MATCH_RESULTS_CHANNEL_ID` at the channel where you want the final score summary to post. Add `CASTER_ROLE_ID`, `REF_ROLE_ID`, `MOD_ROLE_ID`, `MATCH_ASSIGNMENTS_CHANNEL_ID`, and (optionally) `MATCH_STAFF_ALERT_CHANNEL_ID` so staff get pinged when teams submit their time and can claim matches centrally. Fill in `CHALLONGE_USERNAME` / `CHALLONGE_API_KEY` / `CHALLONGE_TOURNAMENT` if you want results pushed to your Challonge bracket.
- **Create**: run `/admin-create-match` and pick two different teams. The bot will open a channel named `[team1]-vs-[team2]` inside the configured category, pre-permission it for both team roles, and ping both team roles in the channel to start the conversation.
- **Reminders**: each match has a 7-day deadline from creation. If no scores are submitted by the deadline, the bot renames the channel with a warning emoji and pings mods.
- **Staff joins**: captains/co-captains run `/submit-time` inside the match channel to post the agreed time. The bot relays that to the assignments channel with claim buttons and pings staff in the alert channel; casters/refs/mods must already hold their staff role to claim, and once a button is claimed it greys out so only one person fills the slot.
- **Score reporting**: captains or co-captains run `/submit-scores` inside the match channel with the first-to-5 scoreline and optional round notes. Both teams must submit matching scores within three attempts; otherwise the bot pings mods. Successful submissions lock the channel, post the requested template to the results channel, and—when configured—update the Challonge bracket.
- **Season flow**: the first six weeks are intended for seeding; after that, move the top 18 teams into a new Challonge bracket. Use `/admin-create-match` to generate fresh channels for each bracket pairing.

## Fast restart when you update your server

Need to pull new code or tweak settings on your DigitalOcean droplet (or any Linux server)?

1. SSH into the machine and go to the project folder, for example:
   ```bash
   cd ~/projects/Transaction-Bot
   ```
2. Activate your virtual environment (create it first if it is missing):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Pull updates and install any new dependencies:
   ```bash
   git pull
   pip install -r requirements.txt
   ```
4. Restart the running bot process:
   * If you launched it in a `tmux`/`screen` session, reattach and press `Ctrl+C`, then run `python -m bot.bot` again.
   * If you set up a `systemd` service (common on droplets), restart it with:
     ```bash
     sudo systemctl restart transaction-bot.service
     ```

The bot will reconnect and re-sync slash commands automatically after the restart.

### Built-in keep-alive web page

The bot now spins up a tiny web server alongside Discord.

1. After the bot starts, open `http://<your-host>:<port>/ping` in a browser (or run `curl http://<your-host>:<port>/ping`). You should see the plain-text response `pong`. Every time that page is loaded, the hosting platform counts it as activity and keeps the container awake.
2. Optional: visit `http://<your-host>:<port>/` to view a JSON health payload that includes the currently connected bot username. This is helpful when debugging deployments.
3. To keep the bot online on free tiers that sleep, configure your uptime checker (UptimeRobot, FreshPing, cron-job.org, etc.) to send an HTTP GET request to the `/ping` URL every 5–10 minutes. The request does not need any headers or body—most hosts just need the endpoint to be hit periodically.

If you change the listening port via `WEB_PORT`, update the URL you monitor accordingly. The default binding is `0.0.0.0:8080`, which most hosts expose automatically.

### Troubleshooting command sync and intents

- **Slash commands are missing in Discord**: Double-check that you invited the bot with both the `bot` and `applications.commands` scopes selected in the OAuth URL generator. If you forgot to include `applications.commands`, regenerate the link, remove the bot from the server, and invite it again. Also make sure the `GUILD_ID` in `.env` matches the server you are testing in—otherwise the commands may take up to an hour to appear globally.
- **“Privileged message content intent is missing” warning**: The bot only uses slash commands, so the warning is harmless. If you want to silence it, open your application in the Developer Portal, go to **Bot > Privileged Gateway Intents**, and toggle **Message Content Intent** on. Restart the bot after saving.
- **403 Forbidden “This server needs more boosts to perform this action”**: Discord only allows uploading role icons on servers with **Level 2** boosts. If your server is not boosted, leave the `profile_picture` field blank when running `/create-team`. The bot will still create the team and simply skip the icon upload.
- **403 Forbidden “Missing Permissions” when assigning roles**: Discord prevents bots from giving out roles that are equal to or higher than the bot’s top role, or when the bot lacks the **Manage Roles** permission. Drag the bot’s role above the captain/member roles in **Server Settings > Roles** and ensure the **Manage Roles** permission is enabled when inviting the bot. The bot now finishes the command and reports which roles it could not assign so you know what to fix.
- **“Couldn't DM … they may have DMs disabled” when inviting a player**: Discord blocks DMs when a user has closed messages from non-friends or from servers they share. Ask the player to enable DMs for the server temporarily, then press the **Invite** button again. The bot only adds the invite after the DM succeeds, so no stale invites remain in the JSON.

## Command summary

| Command | Who can use it | Description |
| --- | --- | --- |
| `/create-team <team_name> <hex_code> <profile_picture> <team_captain>` | Admins | Creates a new team, role, and assigns the captain. |
| `/manage-team` | Captains & co-captains | Interactive roster dashboard with DM-based invites (disabled when roster lock is on or once five players are rostered) plus kick, promote, disband, and transfer options. |
| `/roster` | Everyone | View any team's roster with a searchable dropdown selector. |
| `/leave` | Team members | Leave your current team (captains must transfer or disband first). |
| `/admin-edit` | Admins | Update team name, colour, logo, or captain. |
| `/admin-manage` | Admins | Access the management dashboard for any team with invite access even during roster locks and a force-add button for immediate joins (still capped at five players). |
| `/admin-lock` | Admins | Toggle roster locks to prevent new invites. |
| `/admin-disband-all` | Admins | Triple-confirm wipe of every team, removing roles, clearing rosters, and deleting persisted data. |
| `/admin-create-match <team_one> <team_two> [week]` | Admins | Creates a `[team1]-vs-[team2]` channel in your match category, pings both team roles, adds self-assign buttons for casters/refs/mods, and sets a 7-day deadline. |
| `/submit-time <scheduled_for>` | Captains & co-captains | Run inside the match channel to log the agreed match time, ping both teams, ping staff in the alert channel, and post a claim card to the assignments channel so casters/refs/mods with the right role can accept and gain access. |
| `/submit-scores <your_team_score> <opponent_score> [r1…r5]` | Captains & co-captains | Run inside the match channel to post a first-to-5 result. Both teams must submit the same scoreline; mismatches give three total attempts then ping mods. Successful submissions lock the channel, post the template result, and (when configured) update the Challonge bracket. |
| `/admin-submit-scores <team_one_score> <team_two_score> [r1…r5]` | Admins | Run inside the match channel to force-set a first-to-5 result (forfeit/dispute resolution). Locks the channel, posts the result template, and reports to Challonge when configured. |

> **Who counts as an admin?** Anyone with the Discord “Administrator” server permission _or_ any role ID listed (up to three) in `ADMIN_ROLE_IDS` inside your `.env` file can access the admin-only commands.

## Running the bot on a DigitalOcean Ubuntu droplet (command-line walkthrough)

If you are using a fresh DigitalOcean droplet (for example, Ubuntu 22.04 Premium Intel) and keep your code in `/projects/Transaction-Bot`, this copy/paste guide gets you from a clean machine to a running bot. These steps assume you are SSH’d in as `root`, but they also work for a non-root user with `sudo`.

1. **Install system packages** (Python, git, and the venv helper):
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip git
   ```

2. **Create your projects folder** (skip if it already exists) and clone the repo:
   ```bash
   mkdir -p ~/projects
   cd ~/projects
   git clone https://github.com/your-username/Transaction-Bot.git
   cd Transaction-Bot
   ```

3. **Create the virtual environment.** If you previously saw `No such file or directory` when running `source .venv/bin/activate`, it usually means the `.venv` folder never got created because `python3-venv` was missing. Re-run the venv creation after installing the package in step 1:
   ```bash
   python3 -m venv .venv
   ```

4. **Activate the environment.** This command must be run inside the project folder where `.venv` lives:
   ```bash
   source .venv/bin/activate
   ```
   After activation your prompt should start with `(.venv)`. If it does not, run `ls -a` to confirm the `.venv` directory exists and that you are in `~/projects/Transaction-Bot`.

5. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

6. **Configure your `.env`:**
   ```bash
   cp .env.example .env
   nano .env  # or your preferred editor
   ```
   Fill in `DISCORD_TOKEN`, `GUILD_ID`, and any optional role/channel IDs. Save and exit.

7. **Launch the bot:**
   ```bash
   python -m bot.bot
   ```
   You should see “Logged in as …” plus the keep-alive server binding. Press `Ctrl+C` to stop. To keep the bot running after you log out, consider using a process supervisor like `tmux`, `screen`, or `systemd` (DigitalOcean’s docs show how to create a simple systemd service).

**Quick fix for missing `.venv/bin/activate`:** make sure you ran step 1 (installs `python3-venv`), step 3 (creates the `.venv` folder), and that your shell is in the same directory as `.venv` before activating. If `.venv` exists but activation still fails, delete it (`rm -rf .venv`) and recreate it with `python3 -m venv .venv`.

### Invite flow

- Captains press **Invite** inside `/manage-team`, search for a player, and the bot sends that user a direct message with **Accept** and **Decline** buttons.
- The invite is only stored after the DM is delivered, so you never end up with invites that players cannot see.
- If a player declines (or never responds), captains can re-open `/manage-team` and send another invite whenever they are ready.

### Transaction feed

If you set `TRANSACTIONS_CHANNEL_ID`, the bot posts straightforward plain-text updates using the exact templates below so the feed stays easy to scan:

- Team created

  ```text
  ## New Team Created!

  - Team Name: @TeamRole
  - Team Captain: @CaptainUser
  ```

- Team disbanded

  ```text
  ## Team Team Name has been disbanded
  ```

- Invite accepted

  ```text
  @Player has joined **Team Name**
  ```

- Player left

  ```text
  @Player has left **Team Name**
  ```

- Player promoted to co-captain

  ```text
  @Player has been promoted to co-captain of **Team Name**
  ```

- Captain transferred

  ```text
  @Player is now the captain of **Team Name**
  ```

Substitute the actual Discord mentions where shown and keep the exact structure—no embeds, emoji, or additional decoration.

## Data storage

The bot persists its state in `data/teams.json`. You can back up or edit this file while the bot is offline. The structure includes the roster lock flag, teams, member IDs, and pending invites.

## Contributing

Pull requests are welcome! Please format code with the default `black` settings and ensure new features include documentation updates in this README.
