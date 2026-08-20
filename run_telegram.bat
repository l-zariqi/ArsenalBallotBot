@echo off
title Arsenal Ballot Bot (Telegram)
cd /d "%~dp0"

if not exist venv (
    echo It looks like setup hasn't been run yet.
    echo Double-click setup.bat first, then come back to this.
    pause
    exit /b 1
)

if not exist .env (
    echo No .env file found. Double-click setup.bat first to create one.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Starting the Telegram bot... this window must stay open while it runs.
echo Press Ctrl+C to stop it.
echo.
python bot.py

echo.
echo The bot has stopped. Check the messages above for any errors.
pause
