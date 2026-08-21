# Arsenal Ticket Ballot Alert Bot

Telegram and Discord bots that watch Arsenal FC's public ECAL calendar feed
and alert you the moment a ticket **ballot / registration / sale** window
shows up, plus a reminder before it opens.

## Files

| File                        | What it's for                          |
|------------------------------|-----------------------------------------|
| `bot.py`                    | The Telegram bot                        |
| `discord_bot.py`            | The Discord bot                         |
| `setup.bat` / `setup.sh`    | One-time install                        |
| `run_telegram.bat` / `.sh`  | Starts the Telegram bot                 |
| `run_discord.bat` / `.sh`   | Starts the Discord bot                  |
| `.env.example`              | Copy to `.env` and fill in your token(s) |

You only need to set up the bot(s) you actually want — one doesn't require
the other, and both read the same `.env`.

## First-time setup

1. **Get a bot token**
   - Telegram: message [@BotFather](https://t.me/BotFather) → `/newbot`
   - Discord: create an app at the [Developer Portal](https://discord.com/developers/applications) → **Bot** tab → copy token → under **OAuth2 → URL Generator** tick `bot` + `applications.commands` scopes and `Send Messages` + `Embed Links` permissions, then use the generated link to invite it to your server
2. **Install Python** if you don't have it: [python.org/downloads](https://www.python.org/downloads/) (tick **"Add python.exe to PATH"** on Windows)
3. **Download this project** — GitHub's green **Code** button → **Download ZIP** → unzip
4. **Run setup**
   - Windows: double-click `setup.bat` — it installs everything and opens Notepad for your `.env`
   - Mac/Linux: `chmod +x setup.sh run_telegram.sh run_discord.sh` then `./setup.sh`
5. Paste your token(s) into `.env` after `BOT_TOKEN=` and/or `DISCORD_BOT_TOKEN=`, save, close
6. **Start the bot**
   - Windows: double-click `run_telegram.bat` and/or `run_discord.bat`
   - Mac/Linux: `./run_telegram.sh` and/or `./run_discord.sh`
7. A window opens and stays open — that means it's running.
   - Telegram: message your bot and send `/start`
   - Discord: run `/setalertchannel` in the channel you want alerts in

Closing the window stops that bot. Run both at once by starting both scripts.

## Commands

**Telegram:** `/start` subscribe · `/stop` unsubscribe · `/status` list tracked events · `/check` force a poll

**Discord:** `/setalertchannel` set this channel for alerts (admin) · `/stopalerts` stop alerts here (admin) · `/status` list tracked events · `/check` force a poll

## Running it 24/7

Both scripts only run while the window is open. To keep the bot(s) running
even when your computer is off, host them on an always-on server — see
**DEPLOYMENT.md** for a full walkthrough.