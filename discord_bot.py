"""
Arsenal Ticket Ballot Alert Bot - Discord version
==================================================

Same idea as bot.py (the Telegram version), adapted for Discord: instead of
DMing individual subscribers, this bot posts alerts into one channel per
server (guild), chosen by whoever sets it up with /setalertchannel.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # fill in DISCORD_BOT_TOKEN
    python discord_bot.py
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import discord
import requests
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from icalendar import Calendar

load_dotenv()

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ICS_URL_RAW = os.environ.get(
    "ICS_URL",
    "webcal://ics.ecal.com/ecal-sub/6a8638216e26360002f4aadc/Arsenal%20FC.ics",
)
ICS_URL = ICS_URL_RAW.replace("webcal://", "https://", 1)

POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "15"))
REMINDER_HOURS_BEFORE = int(os.environ.get("REMINDER_HOURS_BEFORE", "24"))

ALERT_KEYWORDS = [
    k.strip().lower()
    for k in os.environ.get(
        "ALERT_KEYWORDS",
        "ballot,registration,register,priority point,members sale,"
        "general sale,ticket sale,membership window",
    ).split(",")
    if k.strip()
]

FALLBACK_URL = os.environ.get("FALLBACK_URL", "https://www.arsenal.com/tickets")

DB_PATH = os.environ.get("DISCORD_DB_PATH", "discord_bot_data.sqlite3")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("arsenal-ballot-discord-bot")


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS alert_channels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS seen_events (
            uid TEXT PRIMARY KEY,
            summary TEXT,
            start_ts TEXT,
            announced INTEGER DEFAULT 0,
            reminded INTEGER DEFAULT 0
        )"""
    )
    return conn


def set_alert_channel(guild_id: int, channel_id: int):
    with db() as conn:
        conn.execute(
            "INSERT INTO alert_channels (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id",
            (guild_id, channel_id),
        )


def clear_alert_channel(guild_id: int):
    with db() as conn:
        conn.execute("DELETE FROM alert_channels WHERE guild_id = ?", (guild_id,))


def get_alert_channels() -> list[int]:
    with db() as conn:
        return [row[0] for row in conn.execute("SELECT channel_id FROM alert_channels")]


def get_guild_channel(guild_id: int) -> int | None:
    with db() as conn:
        row = conn.execute(
            "SELECT channel_id FROM alert_channels WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        return row[0] if row else None


def event_is_known(uid: str) -> bool:
    with db() as conn:
        row = conn.execute("SELECT 1 FROM seen_events WHERE uid = ?", (uid,)).fetchone()
        return row is not None


def store_event(uid: str, summary: str, start_ts: str):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_events (uid, summary, start_ts, announced) "
            "VALUES (?, ?, ?, 1)",
            (uid, summary, start_ts),
        )


def mark_reminded(uid: str):
    with db() as conn:
        conn.execute("UPDATE seen_events SET reminded = 1 WHERE uid = ?", (uid,))


def unreminded_upcoming_events():
    with db() as conn:
        return conn.execute(
            "SELECT uid, summary, start_ts FROM seen_events WHERE reminded = 0"
        ).fetchall()


def all_tracked_events():
    with db() as conn:
        return conn.execute(
            "SELECT summary, start_ts FROM seen_events ORDER BY start_ts"
        ).fetchall()


# --------------------------------------------------------------------------
# ICS fetching / parsing (identical logic to the Telegram version)
# --------------------------------------------------------------------------

def fetch_calendar_events() -> list[dict]:
    resp = requests.get(ICS_URL, timeout=30, headers={"User-Agent": "arsenal-ballot-bot/1.0"})
    resp.raise_for_status()
    cal = Calendar.from_ical(resp.content)

    events = []
    for component in cal.walk("VEVENT"):
        summary = str(component.get("SUMMARY", ""))
        description = str(component.get("DESCRIPTION", ""))
        uid = str(component.get("UID", f"{summary}-{component.get('DTSTART')}"))
        dtstart = component.get("DTSTART")
        start_dt = dtstart.dt if dtstart else None

        if start_dt is not None and not isinstance(start_dt, datetime):
            start_dt = datetime(start_dt.year, start_dt.month, start_dt.day, tzinfo=timezone.utc)
        elif start_dt is not None and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        events.append(
            {
                "uid": uid,
                "summary": summary,
                "description": description,
                "start": start_dt,
                "location": str(component.get("LOCATION", "")),
                "url": str(component.get("URL", "")).strip(),
            }
        )
    return events


def is_ballot_related(event: dict) -> bool:
    haystack = f"{event['summary']} {event['description']}".lower()
    return any(kw in haystack for kw in ALERT_KEYWORDS)


def build_embed(event: dict, reminder: bool = False) -> discord.Embed:
    title = ("\u23F0 Reminder: " if reminder else "\U0001F6A8 New ballot/registration event: ") + event["summary"]
    embed = discord.Embed(
        title=title,
        color=discord.Color.red() if not reminder else discord.Color.orange(),
        url=event.get("url") or FALLBACK_URL,
    )
    if event["start"]:
        embed.add_field(
            name="When", value=event["start"].strftime("%a %d %b %Y, %H:%M UTC"), inline=True
        )
    if event["location"]:
        embed.add_field(name="Where", value=event["location"], inline=True)
    if event["description"]:
        desc = event["description"].strip()
        if len(desc) > 500:
            desc = desc[:500].rsplit(" ", 1)[0] + "\u2026"
        embed.description = desc
    embed.set_footer(text="Arsenal Ticket Ballot Alert Bot")
    return embed


# --------------------------------------------------------------------------
# Discord bot
# --------------------------------------------------------------------------

intents = discord.Intents.default()


class BallotBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        poll_loop.start()


client = BallotBot()


@client.event
async def on_ready():
    log.info("Logged in as %s", client.user)


@client.tree.command(name="setalertchannel", description="Set this channel to receive ballot/registration alerts")
@app_commands.checks.has_permissions(manage_guild=True)
async def setalertchannel(interaction: discord.Interaction):
    set_alert_channel(interaction.guild_id, interaction.channel_id)
    await interaction.response.send_message(
        f"\u2705 Alerts will be posted in {interaction.channel.mention} from now on."
    )


@client.tree.command(name="stopalerts", description="Stop posting alerts in this server")
@app_commands.checks.has_permissions(manage_guild=True)
async def stopalerts(interaction: discord.Interaction):
    clear_alert_channel(interaction.guild_id)
    await interaction.response.send_message("Alerts stopped for this server.")


@client.tree.command(name="status", description="List tracked ballot/registration events")
async def status(interaction: discord.Interaction):
    rows = all_tracked_events()
    if not rows:
        await interaction.response.send_message(
            "No ballot/registration events tracked yet. I'll post here the moment one appears."
        )
        return
    lines = ["**Tracked ballot/registration events:**"]
    for summary, start_ts in rows:
        lines.append(f"\u2022 {summary} \u2014 {start_ts}")
    await interaction.response.send_message("\n".join(lines))


@client.tree.command(name="check", description="Force an immediate check of the calendar")
async def check(interaction: discord.Interaction):
    await interaction.response.send_message("Checking the calendar now\u2026")
    new_count = await poll_and_announce()
    if new_count == 0:
        await interaction.followup.send("No new ballot/registration events found.")
    else:
        await interaction.followup.send(f"Found and announced {new_count} new event(s).")


@setalertchannel.error
@stopalerts.error
async def permission_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need the **Manage Server** permission to use this command.", ephemeral=True
        )
    else:
        raise error


# --------------------------------------------------------------------------
# Core polling logic
# --------------------------------------------------------------------------

async def broadcast(embed: discord.Embed):
    for channel_id in get_alert_channels():
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except Exception as exc:
                log.warning("Could not reach channel %s: %s", channel_id, exc)
                continue
        try:
            await channel.send(embed=embed)
        except Exception as exc:
            log.warning("Failed to post in channel %s: %s", channel_id, exc)


async def poll_and_announce() -> int:
    try:
        events = fetch_calendar_events()
    except Exception as exc:
        log.error("Failed to fetch/parse ICS feed: %s", exc)
        return 0

    ballot_events = [e for e in events if is_ballot_related(e)]
    new_count = 0

    for event in ballot_events:
        if event_is_known(event["uid"]):
            continue
        start_ts = event["start"].isoformat() if event["start"] else ""
        store_event(event["uid"], event["summary"], start_ts)
        new_count += 1
        log.info("New ballot event: %s", event["summary"])
        await broadcast(build_embed(event))

    now = datetime.now(timezone.utc)
    events_by_uid = {e["uid"]: e for e in events}
    for uid, summary, start_ts in unreminded_upcoming_events():
        if not start_ts:
            continue
        start_dt = datetime.fromisoformat(start_ts)
        if now <= start_dt <= now + timedelta(hours=REMINDER_HOURS_BEFORE):
            event = events_by_uid.get(
                uid,
                {"uid": uid, "summary": summary, "description": "", "start": start_dt, "location": "", "url": ""},
            )
            await broadcast(build_embed(event, reminder=True))
            mark_reminded(uid)
            log.info("Sent reminder for: %s", summary)

    return new_count


@tasks.loop(minutes=POLL_INTERVAL_MINUTES)
async def poll_loop():
    await poll_and_announce()


@poll_loop.before_loop
async def before_poll_loop():
    await client.wait_until_ready()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    if not DISCORD_BOT_TOKEN:
        raise SystemExit(
            "Set the DISCORD_BOT_TOKEN environment variable "
            "(create an application + bot at https://discord.com/developers/applications)."
        )
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
