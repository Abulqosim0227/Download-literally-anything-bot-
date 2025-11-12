# 🚀 Setup Guide

Complete step-by-step guide to set up your Media Downloader Bot.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Optional Features](#optional-features)
- [Running the Bot](#running-the-bot)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### 1. Python

**Check if Python is installed:**
```bash
python --version
# or
python3 --version
```

**Install Python 3.8+ if needed:**
- **Windows**: Download from [python.org](https://www.python.org/downloads/)
- **macOS**: `brew install python3`
- **Linux**: `sudo apt install python3 python3-pip`

### 2. Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow the prompts to create your bot
4. Save the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 3. Your Telegram User ID

1. Open Telegram and search for [@userinfobot](https://t.me/userinfobot)
2. Send `/start`
3. Save your user ID (looks like: `123456789`)

### 4. FFmpeg (Optional but Recommended)

FFmpeg enables MP3 conversion. Without it, audio will be in M4A/WEBM format.

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to PATH:
   - Right-click "This PC" → Properties
   - Advanced system settings → Environment Variables
   - Under "System variables", select "Path" → Edit
   - Click "New" and add: `C:\ffmpeg\bin`
   - Click OK on all dialogs
4. Restart your terminal/command prompt

**Verify installation:**
```bash
ffmpeg -version
```

## Installation

### Step 1: Download the Bot

**Option A: Git Clone (Recommended)**
```bash
git clone https://github.com/yourusername/media-downloader-bot.git
cd media-downloader-bot
```

**Option B: Download ZIP**
1. Click the green "Code" button on GitHub
2. Select "Download ZIP"
3. Extract the ZIP file
4. Open terminal/command prompt in the extracted folder

### Step 2: Install Python Dependencies

**Windows:**
```bash
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
pip3 install -r requirements.txt
```

**If you get permission errors:**
```bash
pip install --user -r requirements.txt
```

## Configuration

### Step 1: Create Configuration File

**Linux/macOS:**
```bash
cp config.example.py config.py
```

**Windows (PowerShell):**
```powershell
Copy-Item config.example.py config.py
```

**Windows (Command Prompt):**
```cmd
copy config.example.py config.py
```

### Step 2: Edit Configuration

Open `config.py` in your favorite text editor and fill in:

```python
# Required Settings
BOT_TOKEN = "paste_your_bot_token_here"
ADMIN_ID = your_user_id_here  # Just the number, no quotes

# Optional Settings (can leave as default)
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
```

**Example:**
```python
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
ADMIN_ID = 123456789
```

### Step 3: Save and Close

Make sure to save the file!

## Optional Features

### Music Recognition (Shazam-like)

**Step 1: Sign Up for ACRCloud**

1. Go to [ACRCloud Console](https://console.acrcloud.com/)
2. Sign up for free account
3. Create a new project (Audio & Video Recognition)
4. Note down your credentials:
   - Access Key
   - Access Secret
   - Host (e.g., `identify-eu-west-1.acrcloud.com`)

**Step 2: Enable in config.py**

```python
# Music Recognition
ENABLE_MUSIC_RECOGNITION = True  # Change False to True

# ACRCloud API Credentials
ACRCLOUD_ACCESS_KEY = "your_access_key_here"
ACRCLOUD_ACCESS_SECRET = "your_access_secret_here"
ACRCLOUD_HOST = "identify-eu-west-1.acrcloud.com"  # Your region
```

**Available Regions:**
- Europe: `identify-eu-west-1.acrcloud.com`
- US: `identify-us-west-2.acrcloud.com`
- Asia: `identify-ap-southeast-1.acrcloud.com`

**Free Tier Limits:**
- 2,000 recognitions per day
- Perfect for personal use!

## Running the Bot

### Quick Start

**Windows:**
```bash
python bot.py
```

**Linux/macOS:**
```bash
python3 bot.py
```

### Using Startup Scripts

**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```bash
start.bat
```

### Run in Background

**Linux/macOS:**
```bash
nohup python3 bot.py > bot.log 2>&1 &
```

**Check if running:**
```bash
ps aux | grep bot.py
```

**Stop background process:**
```bash
pkill -f bot.py
```

### Success Indicators

When the bot starts successfully, you'll see:
```
✅ Music recognition feature ENABLED
   (or DISABLED if not configured)
✅ Text search feature ENABLED (admin-only testing)
🤖 Bot started successfully!
```

## First Test

1. Open Telegram
2. Search for your bot (the name you gave it in BotFather)
3. Send `/start`
4. You should see a welcome message!

### Test Downloads

Send any YouTube URL, like:
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### Test Music Recognition (if enabled)

1. Send any audio file or voice message
2. Bot will identify the song!

### Test Song Search (admin only)

```
/search Blinding Lights
```

## Troubleshooting

### Bot doesn't start

**Error: "ModuleNotFoundError"**
```bash
pip install -r requirements.txt
```

**Error: "Invalid bot token"**
- Check `BOT_TOKEN` in `config.py`
- Make sure you copied the entire token
- No extra spaces or quotes

**Error: "Config file not found"**
```bash
cp config.example.py config.py
```

### Bot starts but doesn't respond

**Check if bot is running:**
- Look for error messages in terminal
- Make sure no other instance is running

**Restart the bot:**
- Press `Ctrl+C` to stop
- Run again: `python bot.py`

**Check bot token:**
- Send `/getMe` to [@BotFather](https://t.me/BotFather)
- Make sure your bot is listed

### Downloads fail

**Update yt-dlp:**
```bash
pip install --upgrade yt-dlp
```

**Or via bot:**
```
/updateytdlp
```

### Music recognition doesn't work

**Check credentials:**
- Verify `ENABLE_MUSIC_RECOGNITION = True`
- Check ACRCloud credentials are correct
- Look for error messages in console

**Test credentials:**
```bash
python test_music.py
```

### File "too large" errors

**Solutions:**
- Try lower quality (720p, 480p, 360p)
- Download audio only instead of video
- Telegram limit is 50 MB for bots

### FFmpeg not found

**Install FFmpeg:**
- See [Prerequisites → FFmpeg](#4-ffmpeg-optional-but-recommended)

**Verify installation:**
```bash
ffmpeg -version
```

**Without FFmpeg:**
- Bot still works!
- Audio will be in M4A/WEBM instead of MP3
- Both formats play fine in Telegram

## Advanced Setup

### Run as System Service (Linux)

Create `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Media Downloader Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/full/path/to/media-downloader-bot
ExecStart=/usr/bin/python3 /full/path/to/media-downloader-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

Check status:
```bash
sudo systemctl status telegram-bot
```

View logs:
```bash
sudo journalctl -u telegram-bot -f
```

### Auto-Restart on Failure

The bot includes automatic restart on errors. For additional reliability:

**Create restart script `run_bot.sh`:**
```bash
#!/bin/bash
while true; do
    python3 bot.py
    echo "Bot stopped. Restarting in 5 seconds..."
    sleep 5
done
```

**Make executable and run:**
```bash
chmod +x run_bot.sh
./run_bot.sh
```

### Update yt-dlp Regularly

**Automated (Linux/macOS) - Create cron job:**
```bash
crontab -e
```

Add line:
```
0 2 * * * pip3 install --upgrade yt-dlp
```

This updates yt-dlp every day at 2 AM.

**Manual update:**
```bash
pip install --upgrade yt-dlp
# or use: ./update_ytdlp.sh
```

## Next Steps

- ✅ Bot is running? Great!
- 📖 Read the [README](README.md) for all features
- 👑 Learn admin commands
- 🎵 Enable music recognition
- 🔍 Try song search
- 🌟 Star the repo on GitHub!

## Need Help?

- 📖 Check [README.md](README.md)
- 🐛 Report bugs: [GitHub Issues](https://github.com/yourusername/media-downloader-bot/issues)
- 💡 Suggest features: [GitHub Discussions](https://github.com/yourusername/media-downloader-bot/discussions)

---

Happy downloading! 🎉
