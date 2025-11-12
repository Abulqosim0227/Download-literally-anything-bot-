@echo off
echo Updating yt-dlp...
echo ━━━━━━━━━━━━━━━━━

REM Update yt-dlp
pip install --upgrade yt-dlp

echo.
echo New version:
yt-dlp --version

echo.
echo Update complete!
echo.
echo Restart your bot to apply changes:
echo    1. Stop bot (Ctrl+C)
echo    2. Start bot (python bot.py)
echo.

pause
