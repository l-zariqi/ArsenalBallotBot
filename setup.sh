#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo " Arsenal Ballot Bot - First-time setup"
echo "=========================================="
echo

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 was not found."
    echo "Install it from https://www.python.org/downloads/ (or via your package manager)"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating a virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists, skipping."
fi

echo "Installing required packages..."
source venv/bin/activate
pip install -r requirements.txt --quiet

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo
    echo "A .env file has been created for you."
    echo "Open it now and paste in your bot token from @BotFather:"
    echo "  nano .env      (or open it in any text editor)"
    echo "Find the line starting with BOT_TOKEN= and replace the placeholder."
    read -p "Press Enter to open it in nano now, or Ctrl+C to edit it yourself later..."
    ${EDITOR:-nano} .env
else
    echo ".env already exists, leaving it as-is."
fi

echo
echo "=========================================="
echo " Setup complete!"
echo " Run ./run.sh to start the bot."
echo "=========================================="
