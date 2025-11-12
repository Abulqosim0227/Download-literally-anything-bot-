@echo off
echo Starting Media Downloader Bot...
echo ================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed
    pause
    exit /b 1
)

REM Check if FFmpeg is installed
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo Warning: FFmpeg is not installed. Audio extraction may not work.
    echo Download from: https://ffmpeg.org/download.html
    echo.
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update requirements
echo Installing dependencies...
pip install -q --upgrade pip
pip install -q -r requirements.txt

REM Create downloads directory
if not exist "downloads" mkdir downloads

REM Run the bot
echo.
echo Bot is starting...
echo Press Ctrl+C to stop
echo ================================
python bot.py

pause
