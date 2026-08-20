@echo off
setlocal enabledelayedexpansion
title Arsenal Ballot Bot - Setup
cd /d "%~dp0"

echo ==========================================
echo  Arsenal Ballot Bot - First-time setup
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Install it from https://www.python.org/downloads/
    echo IMPORTANT: on the install screen, tick "Add python.exe to PATH".
    echo Then run this setup.bat again.
    pause
    exit /b 1
)

if not exist venv (
    echo Creating a virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists, skipping.
)

echo Installing required packages...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install packages. See the error above.
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo A .env file has been created for you.
    echo Notepad will now open so you can paste in your bot token.
    echo Find the line that starts with BOT_TOKEN= and replace the
    echo placeholder with the token @BotFather gave you on Telegram.
    echo Save the file and close Notepad to continue.
    pause
    notepad .env
) else (
    echo .env already exists, leaving it as-is.
)

echo.
echo ==========================================
echo  Setup complete!
echo  Double-click run.bat to start the bot.
echo ==========================================
pause
