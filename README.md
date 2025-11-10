# League Management Discord Bot

A Discord bot built with [`discord.py`](https://discordpy.readthedocs.io/en/stable/) that manages competitive teams inside a server. Administrators can create teams, captains can manage rosters, and players can accept invites — all powered by slash commands and persistent JSON storage.

## Features

- `/create-team` automatically creates a coloured role, assigns a captain, and stores metadata in `data/teams.json`.
- `/manage-team` gives captains and co-captains a management dashboard with invite, kick, promote, disband, and transfer controls, sending direct-message invites that players can accept or decline instantly.
- Optional transaction feed posts simple text updates whenever teams are created, captains change, players join/leave, or other roster actions occur.
- `/leave` lets non-captain members leave their team after confirmation.
- `/admin-edit`, `/admin-manage`, `/admin-lock`, and `/admin-disband-all` offer complete administrative control, including roster locks, forced additions, and mass disbands.

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
     - `TRANSACTIONS_CHANNEL_ID` (optional): a text channel ID where the bot will post roster changes, team creations, and other updates.
     - `ADMIN_ROLE_IDS` (optional): a comma-separated list (up to three) of role IDs (for example `123,456`) whose members should be treated as bot admins even if they don't have the Discord-wide Administrator permission.
     - `WEB_HOST` / `WEB_PORT` (optional): override the mini status site's bind address (defaults to `0.0.0.0:8080`). Leave these blank to accept the defaults on free hosting providers.

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

### Built-in keep-alive web page

The bot now spins up a tiny web server alongside Discord.

1. After the bot starts, open `http://<your-host>:<port>/ping` in a browser (or run `curl http://<your-host>:<port>/ping`). You should see the plain-text response `pong`. Every time that page is loaded, the hosting platform counts it as activity and keeps the container awake.
2. Optional: visit `http://<your-host>:<port>/` to view a JSON health payload that includes the currently connected bot username. This is helpful when debugging deployments.
3. To keep the bot online on free tiers that sleep, configure your uptime checker (UptimeRobot, FreshPing, cron-job.org, etc.) to send an HTTP GET request to the `/ping` URL every 5–10 minutes. The request does not need any headers or body—Render and similar providers only require that the endpoint is hit periodically.

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
| `/manage-team` | Captains & co-captains | Interactive roster dashboard with DM-based invites (disabled when roster lock is on) plus kick, promote, disband, and transfer options. |
| `/roster` | Everyone | View any team's roster with a searchable dropdown selector. |
| `/leave` | Team members | Leave your current team (captains must transfer or disband first). |
| `/admin-edit` | Admins | Update team name, colour, logo, or captain. |
| `/admin-manage` | Admins | Access the management dashboard for any team with invite access even during roster locks and a force-add button for immediate joins. |
| `/admin-lock` | Admins | Toggle roster locks to prevent new invites. |
| `/admin-disband-all` | Admins | Triple-confirm wipe of every team, removing roles, clearing rosters, and deleting persisted data. |

> **Who counts as an admin?** Anyone with the Discord “Administrator” server permission _or_ any role ID listed (up to three) in `ADMIN_ROLE_IDS` inside your `.env` file can access the admin-only commands.

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

## Free hosting on Render (beginner friendly)

Render's free **Web Service** tier can run the bot continuously as long as the service receives an HTTP request at least once every 30 minutes. The built-in `/ping` endpoint was added specifically for this workflow. These steps assume your code lives on GitHub, but Render also supports GitLab and Bitbucket.

1. **Prepare your repository**
   - Push this project to a GitHub repository (either public or private). Render deploys directly from your git history.
   - Double-check that `.env` is listed in `.gitignore` so you never push secrets.

2. **Create a Render account**
   - Sign up or log in at [render.com](https://render.com/). The free plan is enough for this bot.

3. **Create a new Web Service**
   - From the Render dashboard, click **New > Web Service**.
   - Connect your GitHub account if prompted, then choose the repository containing the bot.
   - For **Name**, pick something like `transaction-bot`.
   - Set **Region** to the closest option to your Discord servers for lower latency.
   - Choose the **Free** instance type.

4. **Configure the build and start commands**
   - In the **Build Command** box, enter:
     ```bash
     pip install -r requirements.txt
     ```
   - In the **Start Command** box, set:
     ```bash
     WEB_PORT=$PORT python -m bot.bot
     ```
     Render injects a dynamic `PORT` value at runtime; exporting `WEB_PORT=$PORT` before starting the bot makes the keep-alive site bind to the correct port.

5. **Add environment variables**
   - Scroll to the **Environment Variables** section and add the same keys you would place in your local `.env` file:
     - `DISCORD_TOKEN`
     - `GUILD_ID` (optional but recommended for faster slash-command sync)
     - `CAPTAIN_ROLE_ID`, `CO_CAPTAIN_ROLE_ID`, `TEAM_MEMBER_ROLE_ID` (optional role IDs)
     - `TRANSACTIONS_CHANNEL_ID` (optional)
     - `ADMIN_ROLE_IDS` (optional comma-separated list)
     - `WEB_HOST` set to `0.0.0.0` (ensures the aiohttp server listens on all interfaces)
   - You do **not** need to add `WEB_PORT` manually because the start command already exports it.

6. **Deploy**
   - Click **Create Web Service**. Render installs dependencies, runs migrations (none in this project), and finally executes the start command.
   - Wait for the logs to show `Started status site on http://0.0.0.0:<port>` followed by `Logged in as ...`. When that appears, the bot is online.

7. **Keep the service awake**
   - Render pauses free services after 15 minutes of inactivity. Use an external uptime pinger (for example, UptimeRobot or cron-job.org) to send an HTTP GET request to `https://<your-service-name>.onrender.com/ping` every 5–10 minutes. Each ping keeps the process active and simultaneously confirms the bot is still responsive.

8. **Deploy updates**
   - Push commits to your repository. Render automatically redeploys the latest commit on the selected branch.
   - Watch the Render deploy logs to ensure the bot reconnects successfully after each update.

If anything fails, open the Render service logs. They show the same startup messages you see locally, including configuration errors, missing environment variables, or Discord authentication problems.

## Free hosting on Oracle Cloud (beginner friendly)

You can run the bot 24/7 without paying by using Oracle Cloud Infrastructure's **Always Free** tier. The checklist below assumes you have never touched Oracle before and walks you through spinning up an Ubuntu server and keeping the bot online.

1. **Create (or sign in to) an Oracle Cloud account**
   - Go to [cloud.oracle.com/free](https://www.oracle.com/cloud/free/) and create an account.
   - During sign-up Oracle asks for credit-card details for verification, but the Always Free resources will not charge you.
   - After the account is activated, sign in to the [Oracle Cloud Console](https://cloud.oracle.com/). The first login can take a minute while the tenancy is provisioned.

2. **Launch an Always Free compute instance**
   - In the console search bar, type **"Compute Instances"** and open it.
   - Click **Create instance**.
   - Give it a name like `transaction-bot` and ensure the **Compartment** is your root compartment.
   - Under **Image and shape**, pick **Canonical Ubuntu 22.04** (or any Ubuntu LTS) and click **Change shape**. Select an **Always Free eligible** shape, such as `VM.Standard.A1.Flex` with 1 OCPU and 1 GB of RAM.
   - Leave networking on the default VCN/subnet. Make sure **Assign a public IPv4 address** stays checked so you can SSH in.
   - In the **Add SSH keys** section, choose **Generate SSH key pair** and download both the private and public key files. Oracle shows their paths after creation; you'll use the `.key` file in the next step.
   - Click **Create** and wait for the instance state to switch to *Running*.

3. **Connect to the VM**
   - Note the instance's public IP address from the instance details page.
   - On Windows, install [Git for Windows](https://gitforwindows.org/) or [PuTTY](https://www.putty.org/) if you do not already have an SSH client.
     - **Git Bash / macOS / Linux**: open a terminal and run `chmod 600 path/to/private.key`, then connect with:
       ```bash
       ssh -i path/to/private.key ubuntu@YOUR_PUBLIC_IP
       ```
     - **PuTTY**: convert the downloaded private key to PuTTY's `.ppk` format using *PuTTYgen*, then connect to `ubuntu@YOUR_PUBLIC_IP`.
   - The default user for Ubuntu images is `ubuntu`. Accept the fingerprint prompt on the first connection.

4. **Install system packages and Python**
   - Update packages:
     ```bash
     sudo apt update && sudo apt upgrade -y
     ```
   - Install Git, Python, and virtualenv tools:
     ```bash
     sudo apt install -y git python3 python3-venv python3-pip
     ```

5. **Deploy the bot code**
   - Clone the repository and enter it:
     ```bash
     git clone https://github.com/YOUR_USERNAME/Transaction-Bot.git
     cd Transaction-Bot
     ```
     Replace the URL if you forked or host it elsewhere.
   - Create and activate a virtual environment:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - Install requirements:
     ```bash
     pip install -r requirements.txt
     ```
   - Copy the environment template and edit it:
     ```bash
     cp .env.example .env
     nano .env
     ```
     Paste your Discord token, guild ID, role IDs, and (optionally) the transactions channel ID. Press `Ctrl+O` then `Ctrl+X` to save in Nano.

6. **Test the bot manually**
   - Still inside the virtual environment, run:
     ```bash
     python -m bot.bot
     ```
   - Confirm the bot logs in and your slash commands appear. Stop it with `Ctrl+C` after verifying everything works.

7. **Keep the bot running after you disconnect**
   - The quickest approach is to use [`tmux`](https://github.com/tmux/tmux/wiki) or [`screen`](https://www.gnu.org/software/screen/). Install tmux and start a session:
     ```bash
     sudo apt install -y tmux
     tmux new -s bot
     ```
   - Activate the virtual environment inside tmux and start the bot again:
     ```bash
     cd ~/Transaction-Bot
     source .venv/bin/activate
     python -m bot.bot
     ```
   - Detach from tmux with `Ctrl+B` then `D`. The bot keeps running even if you close the SSH window. Reattach later with `tmux attach -t bot`.

   > **Want a more permanent setup?** Create a simple `systemd` service that launches the bot on boot. Oracle's docs cover enabling custom services, but tmux is perfectly fine for Always Free instances.

8. **Secure your instance**
   - Keep the system updated (`sudo apt update && sudo apt upgrade -y` weekly).
   - Rotate your Discord token if it ever leaks—update `.env` and restart the bot.
   - Store a backup of `data/teams.json` periodically (`scp ubuntu@YOUR_PUBLIC_IP:~/Transaction-Bot/data/teams.json ./backup.json`).

Whenever you need to deploy updates, SSH back in, `cd` into the repo, pull the latest changes (`git pull`), reactivate `.venv`, and restart the bot inside your tmux session.
