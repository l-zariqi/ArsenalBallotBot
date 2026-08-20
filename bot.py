"""
Arsenal Ticket Ballot Alert Bot
================================

Polls Arsenal FC's public ECAL calendar feed (ICS format) and sends a
Telegram message to subscribed chats whenever a new event shows up whose
title/description looks like a ticket ballot / registration window
(configurable keywords), plus an optional reminder shortly before it opens.

Storage: a local SQLite file (subscribers + events we've already alerted on),
so restarts don't cause duplicate or missed alerts.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # fill in BOT_TOKEN
    python bot.py
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from icalendar import Calendar

load_dotenv()
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ICS_URL_RAW = os.environ.get(
    "ICS_URL",
    "webcal://ics.ecal.com/ecal-sub/6a8638216e26360002f4aadc/Arsenal%20FC.ics",
)
# webcal:// isn't an HTTP scheme — swap it for https:// so requests can fetch it
ICS_URL = ICS_URL_RAW.replace("webcal://", "https://", 1)

POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "15"))
REMINDER_HOURS_BEFORE = int(os.environ.get("REMINDER_HOURS_BEFORE", "24"))

# Keywords that mark an event as ballot/registration-related (case-insensitive,
# matched against the event SUMMARY + DESCRIPTION). Edit to taste.
ALERT_KEYWORDS = [
    k.strip().lower()
    for k in os.environ.get(
        "ALERT_KEYWORDS",
        "ballot,registration,register,priority point,members sale,"
        "general sale,ticket sale,membership window",
    ).split(",")
    if k.strip()
]

DB_PATH = os.environ.get("DB_PATH", "bot_data.sqlite3")

# Used when an event has no URL of its own
FALLBACK_URL = os.environ.get("FALLBACK_URL", "https://www.arsenal.com/tickets")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("arsenal-ballot-bot")


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS subscribers (chat_id INTEGER PRIMARY KEY)"
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


def add_subscriber(chat_id: int):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (chat_id,)
        )


def remove_subscriber(chat_id: int):
    with db() as conn:
        conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))


def get_subscribers() -> list[int]:
    with db() as conn:
        return [row[0] for row in conn.execute("SELECT chat_id FROM subscribers")]


def event_is_known(uid: str) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_events WHERE uid = ?", (uid,)
        ).fetchone()
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


# --------------------------------------------------------------------------
# ICS fetching / parsing
# --------------------------------------------------------------------------

def fetch_calendar_events() -> list[dict]:
    """Download and parse the ICS feed. Returns a list of event dicts."""
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

        # DTSTART can be a date or a datetime; normalize to an aware datetime
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


# --------------------------------------------------------------------------
# Telegram handlers
# --------------------------------------------------------------------------

WELCOME = (
    "\U0001F534\u26AA\uFE0F Arsenal Ticket Ballot Alerts\n\n"
    "You're subscribed. I'll message you here as soon as a new ballot / "
    "registration / sale window shows up on Arsenal's official fixtures & "
    "events calendar, plus a reminder before it opens.\n\n"
    "Commands:\n"
    "/status \u2013 show upcoming ballot-related events I know about\n"
    "/check \u2013 force a check right now\n"
    "/stop \u2013 unsubscribe"
)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_subscriber(update.effective_chat.id)
    await update.message.reply_text(WELCOME)


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remove_subscriber(update.effective_chat.id)
    await update.message.reply_text("Unsubscribed \u2014 you won't get any more alerts. Send /start to rejoin any time.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute(
            "SELECT summary, start_ts FROM seen_events ORDER BY start_ts"
        ).fetchall()
    if not rows:
        await update.message.reply_text(
            "No ballot/registration events tracked yet. I'll message you the moment one appears."
        )
        return
    lines = ["Tracked ballot/registration events:"]
    for summary, start_ts in rows:
        lines.append(f"\u2022 {summary} \u2014 {start_ts}")
    await update.message.reply_text("\n".join(lines))


async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Checking the calendar now\u2026")
    new_count = await poll_and_announce(context.application)
    if new_count == 0:
        await update.message.reply_text("No new ballot/registration events found.")
    else:
        await update.message.reply_text(f"Found and announced {new_count} new event(s).")


# --------------------------------------------------------------------------
# Core polling logic
# --------------------------------------------------------------------------

async def broadcast(app: Application, text: str):
    subs = get_subscribers()
    for chat_id in subs:
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as exc:  # e.g. user blocked the bot
            log.warning("Failed to message %s: %s", chat_id, exc)


def format_event_alert(event: dict, reminder: bool = False) -> str:
    when = event["start"].strftime("%a %d %b %Y, %H:%M UTC") if event["start"] else "Date TBC"
    header = "\u23F0 <b>Reminder</b>" if reminder else "\U0001F6A8 <b>New ballot/registration event</b>"
    text = f"{header}\n\n<b>{event['summary']}</b>\n\U0001F4C5 {when}"
    if event["location"]:
        text += f"\n\U0001F4CD {event['location']}"
    if event["description"]:
        desc = event["description"].strip()
        if len(desc) > 400:
            desc = desc[:400].rsplit(" ", 1)[0] + "\u2026"
        text += f"\n\n{desc}"

    link = event.get("url") or FALLBACK_URL
    if link:
        text += f"\n\n\U0001F517 {link}"
    return text


async def poll_and_announce(app: Application) -> int:
    """Fetch the calendar, announce new matching events, send due reminders.
    Returns the number of newly-announced events."""
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
        await broadcast(app, format_event_alert(event))

    # Reminders for events starting soon
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
            await broadcast(app, format_event_alert(event, reminder=True))
            mark_reminded(uid)
            log.info("Sent reminder for: %s", summary)

    return new_count


async def poll_job(context: ContextTypes.DEFAULT_TYPE):
    await poll_and_announce(context.application)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Set the BOT_TOKEN environment variable (get one from @BotFather on Telegram)."
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("check", check_cmd))

    app.job_queue.run_repeating(
        poll_job, interval=POLL_INTERVAL_MINUTES * 60, first=10
    )

    log.info(
        "Starting bot. Polling %s every %s minutes.", ICS_URL, POLL_INTERVAL_MINUTES
    )
    app.run_polling()


if __name__ == "__main__":
    main()
