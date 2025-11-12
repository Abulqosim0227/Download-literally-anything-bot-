# Configuration file for Media Downloader Bot
#
# INSTRUCTIONS:
# 1. Rename this file to 'config.py'
# 2. Fill in your actual credentials below
# 3. Never commit config.py to GitHub (it's in .gitignore)

# ==============================================================================
# REQUIRED: Bot Configuration
# ==============================================================================
# Get your bot token from @BotFather on Telegram
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Example: "1234567890:ABCdefGhIjKlmNoPQRsTUVwxyZ"

# Your Telegram user ID (get it from @userinfobot)
ADMIN_ID = 0  # Example: 1234567890

# ==============================================================================
# Download Settings
# ==============================================================================
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (Telegram limit is 50MB for bots)

# ==============================================================================
# Supported Platforms
# ==============================================================================
SUPPORTED_PLATFORMS = [
    "YouTube",
    "Instagram",
    "TikTok",
    "Facebook",
    "Twitter/X",
    "Reddit",
    "Vimeo"
]

# ==============================================================================
# Quality Options
# ==============================================================================
VIDEO_QUALITIES = {
    "best": "Best Quality",
    "1080p": "1080p (Full HD)",
    "720p": "720p (HD)",
    "480p": "480p (SD)",
    "360p": "360p (Low)"
}

AUDIO_FORMATS = {
    "mp3": "MP3 (Best Quality)",
    "m4a": "M4A (AAC)",
    "opus": "OPUS"
}

# ==============================================================================
# OPTIONAL: Music Recognition Feature (Shazam-like)
# ==============================================================================
# Set to True to enable music recognition from audio/voice messages
# Set to False to disable (bot will work normally without this feature)
ENABLE_MUSIC_RECOGNITION = False  # ← Change to True to enable

# ACRCloud API Credentials
# Sign up at: https://www.acrcloud.com/
# FREE tier: 2000 recognitions/day
ACRCLOUD_ACCESS_KEY = ""  # Your ACRCloud access key
ACRCLOUD_ACCESS_SECRET = ""  # Your ACRCloud access secret
ACRCLOUD_HOST = "identify-eu-west-1.acrcloud.com"  # Choose your region:
# Europe: identify-eu-west-1.acrcloud.com
# US: identify-us-west-2.acrcloud.com
# Asia: identify-ap-southeast-1.acrcloud.com

# Note: If ENABLE_MUSIC_RECOGNITION is False, the bot works exactly as before
# This feature is 100% optional and doesn't affect video downloads!
