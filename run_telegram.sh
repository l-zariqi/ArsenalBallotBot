#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "It looks like setup hasn't been run yet."
    echo "Run ./setup.sh first, then come back to this."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "No .env file found. Run ./setup.sh first to create one."
    exit 1
fi

source venv/bin/activate
echo "Starting the Telegram bot... this terminal must stay open while it runs."
echo "Press Ctrl+C to stop it."
echo
python bot.py
