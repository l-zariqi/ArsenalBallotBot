# Arsenal Ticket Ballot Alert Bot

A Telegram bot that watches Arsenal FC's public ECAL calendar feed and pings
subscribers the moment a ticket **ballot / registration / sale** window shows
up, plus a reminder before it opens.

## How it works

1. Every `POLL_INTERVAL_MINUTES` (default 15) it downloads the ICS feed:
   `webcal://ics.ecal.com/ecal-sub/6a8638216e26360002f4aadc/Arsenal%20FC.ics`
2. It scans each calendar event's title + description for keywords like
   `ballot`, `registration`, `priority point`, `members sale`, etc.
   (fully configurable — see `.env.example`).
3. Any newly-seen matching event is broadcast to every subscribed chat.
4. It also sends a one-off reminder `REMINDER_HOURS_BEFORE` (default 24h)
   before a matched event's start time.
5. State (subscribers + which events have already been announced/reminded)
   lives in a local SQLite file, so restarts don't cause duplicate spam.

**Note on the feed itself:** the calendar is Arsenal's general fixtures/events
feed, not a ballot-specific one. This bot filters it by keyword, so if Arsenal
ever phrases things differently than expected (e.g. "Cup Ballot" vs "Ticket
Ballot"), just add the new phrase to `ALERT_KEYWORDS` in `.env`. Run `/status`
any time to see exactly which events the bot currently considers "matches" —
that's the fastest way to tell if the keyword list needs tweaking.

## Quick start (no terminal experience needed)

1. **Create the bot**: message [@BotFather](https://t.me/BotFather) on
   Telegram, run `/newbot`, and copy the token it gives you.
2. **Install Python** if you don't have it: [python.org/downloads](https://www.python.org/downloads/).
   On Windows, tick **"Add python.exe to PATH"** on the install screen.
3. **Download this project** — on GitHub, click the green **Code** button →
   **Download ZIP**, then unzip it wherever you like.
4. **Windows**: double-click `setup.bat`. It creates everything it needs and
   opens Notepad for you to paste in your bot token — paste it after
   `BOT_TOKEN=`, save, close Notepad.
   **Mac/Linux**: open a terminal in the folder and run `./setup.sh` once
   (you may need `chmod +x setup.sh run_telegram.sh run_discord.sh` first).
5. **Windows**: double-click `run_telegram.bat` to start the bot.
   **Mac/Linux**: run `./run_telegram.sh`.
6. A black window will open and stay open — that means it's running. Go to
   Telegram, open a chat with your bot, and send `/start`.

Closing that window stops the bot. To run it again later, just double-click
`run_telegram.bat` (or `./run_telegram.sh`) — you don't need to repeat setup.

For a bot that keeps running even when your computer is off, see
**"Running it 24/7"** below.

## Discord version

`discord_bot.py` is the same alerting logic ported to Discord. Since a Discord
server is shared rather than 1:1 like a Telegram DM, it works a bit
differently: instead of subscribing individual users, an admin picks **one
channel per server** to receive alerts, posted as rich embeds.

### Setting it up

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   → **New Application** → give it a name.
2. Open the **Bot** tab → **Reset Token** → copy it. This goes in `.env` as
   `DISCORD_BOT_TOKEN`.
3. Still on the Bot tab, you don't need any privileged intents (Message
   Content, Presence, etc.) — this bot only uses slash commands and doesn't
   read message content.
4. Go to **OAuth2 → URL Generator**. Under **Scopes** tick `bot` and
   `applications.commands`. Under **Bot Permissions** tick `Send Messages`
   and `Embed Links`. Copy the generated URL, open it in a browser, and
   invite the bot to your server.
5. **Windows**: run `setup.bat` if you haven't already (it installs both the
   Telegram and Discord dependencies), then double-click `run_discord.bat`.
   **Mac/Linux**: `./setup.sh` then `./run_discord.sh`.
6. In your server, run `/setalertchannel` in whichever channel you want
   alerts posted to. (Requires the **Manage Server** permission.)

### Commands

| Command             | What it does                                          |
|----------------------|--------------------------------------------------------|
| `/setalertchannel`  | Post alerts in the channel this was run in (admin only) |
| `/stopalerts`       | Stop posting alerts in this server (admin only)        |
| `/status`           | List every ballot/registration event tracked so far    |
| `/check`            | Force an immediate poll of the calendar                |

It shares the same `.env` settings as the Telegram bot (`ICS_URL`,
`ALERT_KEYWORDS`, `POLL_INTERVAL_MINUTES`, `REMINDER_HOURS_BEFORE`,
`FALLBACK_URL`) — set them once and both bots use them. You can run either
bot on its own, or both at the same time (they use separate database files
so they won't interfere with each other).

1. **Create the bot**: message [@BotFather](https://t.me/BotFather) on
   Telegram, run `/newbot`, and copy the token it gives you.

2. **Install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure**:
   ```bash
   cp .env.example .env
   # edit .env and paste your BOT_TOKEN
   ```

4. **Run it**:
   ```bash
   python bot.py
   ```

5. In Telegram, open a chat with your bot and send `/start` to subscribe.
   Anyone who sends `/start` to the bot gets added to the alert list; `/stop`
   removes them.

## Commands

| Command   | What it does                                              |
|-----------|-------------------------------------------------------------|
| `/start`  | Subscribe this chat to alerts                              |
| `/stop`   | Unsubscribe                                                 |
| `/status` | List every ballot/registration event the bot has tracked   |
| `/check`  | Force an immediate poll of the calendar (useful for testing) |

## Running it 24/7

For it to actually alert people you need it running continuously somewhere,
not just on your laptop. Cheapest options:

- A small VPS (e.g. a $4–6/mo box) + `systemd` service or `tmux`/`screen`
- A free-tier always-on host (Railway, Fly.io, a Raspberry Pi at home, etc.)
- Docker: wrap this in a container and run it under any container host

A minimal `systemd` unit, for example:

```ini
[Unit]
Description=Arsenal Ballot Alert Bot
After=network.target

[Service]
WorkingDirectory=/opt/arsenal-ballot-bot
ExecStart=/opt/arsenal-ballot-bot/venv/bin/python bot.py
Restart=always
EnvironmentFile=/opt/arsenal-ballot-bot/.env

[Install]
WantedBy=multi-user.target
```

## Sending alerts to a group instead of DMs

Add the bot to a Telegram group, send `/start` **in that group** (make it an
admin if you want it to post without restriction), and the group's chat ID
gets subscribed the same way a personal chat would.

## Adjusting sensitivity

- Too many irrelevant alerts → tighten `ALERT_KEYWORDS` in `.env` (fewer,
  more specific terms).
- Missed an event → check `/status` to see what the bot picked up, and widen
  `ALERT_KEYWORDS` if the actual wording Arsenal used wasn't covered.

## Uploading this to GitHub

The included `.gitignore` already excludes the two things you must never
commit:

- `.env` — contains your real bot token. Only `.env.example` (with a fake
  placeholder token) should ever be pushed.
- `bot_data.sqlite3` — your local subscriber list and event history; it's
  machine-specific and shouldn't be shared.

If you ever *do* accidentally commit your real token, treat it as
compromised: message @BotFather, run `/revoke`, and generate a new one.
