# 🎵 Media Downloader Bot

A powerful Telegram bot that downloads videos and audio from multiple social media platforms with **Music Recognition** (Shazam-like), **Song Search**, and **2GB File Support**!

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg?logo=telegram)

</div>

## ✨ Features

### 🎥 Media Download
- **Multi-Platform Support**: Download from YouTube, Instagram, TikTok, Facebook, Twitter/X, Reddit, Vimeo, and more
- **🚀 2GB File Support**: Upload files up to 2GB (not just 50MB!)
- **Smart Upload System**: Automatically uses best method based on file size
  - Files < 50MB → Bot API (fast)
  - Files 50MB-2GB → Client API (Pyrogram)
- **Multiple Quality Options**: Choose from Best, 1080p, 720p, 480p, or 360p
- **Audio Extraction**: Extract audio in MP3, M4A, or OPUS format
- **User-Friendly Interface**: Interactive inline keyboards for easy navigation
- **Fast Downloads**: Powered by yt-dlp for reliable and fast downloads

### 🎵 Music Recognition (Optional)
- **Shazam-like Functionality**: Send any audio file or voice message to identify songs
- **Accurate Recognition**: Powered by ACRCloud audio fingerprinting
- **Instant Results**: Get song title, artist, album, and release year
- **YouTube Integration**: Direct links to find the song on YouTube
- **Cover Song Detection**: Identifies covers and remixes

### 🔍 Song Search (Admin Testing)
- **Text-based Search**: Search for songs by name, artist, or lyrics
- **iTunes Integration**: Search millions of songs (no API key required!)
- **Auto-Download**: Automatically finds and downloads songs from YouTube
- **Interactive Results**: Select from 5 search results with one click
- **Smart Fallback**: Manual YouTube search if auto-download fails

### 👑 Admin Features
- **Comprehensive Admin Panel**: Full control via interactive dashboard
- **User Management**: View all users, track activity, ban/unban users
- **Advanced Statistics**: Platform-wise stats, top users, download trends
- **Ban System**: Protect your bot from abuse
- **Download History**: Monitor recent downloads across all users
- **Data Persistence**: All data saved to JSON database

## 📋 Prerequisites

- Python 3.8 or higher
- FFmpeg (optional but recommended for audio conversion)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Installing FFmpeg

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
2. Extract and add to PATH

**Note:** Bot works without FFmpeg, but audio will be in original format (M4A/WEBM) instead of MP3.

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/media-downloader-bot.git
cd media-downloader-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the Bot

```bash
cp config.example.py config.py
```

Edit `config.py` and set:
- `BOT_TOKEN`: Your bot token from [@BotFather](https://t.me/BotFather)
- `ADMIN_ID`: Your Telegram user ID from [@userinfobot](https://t.me/userinfobot)

**Optional - Enable 2GB File Support:**
1. Get API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
2. See detailed guide: [GET_API_CREDENTIALS.md](GET_API_CREDENTIALS.md)
3. Set in `config.py`:
   - `ENABLE_LARGE_FILES = True`
   - `API_ID` (your api_id)
   - `API_HASH` (your api_hash)
4. Install: `pip install pyrogram tgcrypto`

**Optional - Enable Music Recognition:**
1. Sign up at [ACRCloud](https://www.acrcloud.com/) (FREE: 2000 recognitions/day)
2. Get your credentials from the console
3. Set in `config.py`:
   - `ENABLE_MUSIC_RECOGNITION = True`
   - `ACRCLOUD_ACCESS_KEY`
   - `ACRCLOUD_ACCESS_SECRET`
   - `ACRCLOUD_HOST`

### 4. Run the Bot

```bash
python bot.py
```

Or use the startup scripts:
- Linux/Mac: `./start.sh`
- Windows: `start.bat`

## 📖 Usage

### For Users

**Download Media:**
1. Send any video URL to the bot
2. Choose your preferred quality or format
3. Wait for the download and enjoy!

**Identify Music:**
1. Send any audio file or voice message
2. Bot will identify the song
3. Get song details and YouTube link

**Commands:**
- `/start` - Welcome message and quick links
- `/help` - Detailed instructions
- `/search <song name>` - Search for songs (admin only during testing)

### For Admins

**Admin Commands:**
- `/admin` - Open admin dashboard
- `/ban <user_id>` - Ban a user
- `/unban <user_id>` - Unban a user
- `/stats` - Quick statistics
- `/search <query>` - Search and auto-download songs
- `/updateytdlp` - Update yt-dlp
- `/version` - Check yt-dlp version

## 🎨 Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| YouTube | ✅ | Videos, Shorts, Playlists |
| Instagram | ✅ | Posts, Reels, IGTV, Stories |
| TikTok | ✅ | Videos (use direct share links) |
| Facebook | ✅ | Public videos only |
| Twitter/X | ✅ | Videos and GIFs |
| Reddit | ✅ | Videos from v.redd.it |
| Vimeo | ✅ | Public videos |
| Dailymotion | ✅ | All videos |
| Twitch | ✅ | Clips and VODs |
| And many more! | ✅ | Powered by yt-dlp |

## 🔧 Configuration

### Core Settings (`config.py`)

```python
# Required
BOT_TOKEN = "your_bot_token"
ADMIN_ID = your_telegram_id

# Optional
DOWNLOAD_DIR = "downloads"  # Temporary download folder
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (Telegram limit)

# Music Recognition (optional)
ENABLE_MUSIC_RECOGNITION = False  # Set to True to enable
ACRCLOUD_ACCESS_KEY = "your_key"
ACRCLOUD_ACCESS_SECRET = "your_secret"
ACRCLOUD_HOST = "identify-eu-west-1.acrcloud.com"
```

## 🐛 Troubleshooting

### Common Issues

**TikTok/Facebook not working?**
```bash
pip install --upgrade yt-dlp
# or use bot command: /updateytdlp
```

**"Cannot parse data" error:**
- Platform updated → Update yt-dlp
- Wait 24-48h after platform updates

**File too large:**
- Try lower quality (720p, 480p, 360p)
- Or download audio only

**Music recognition not working:**
- Check ACRCloud credentials
- Verify `ENABLE_MUSIC_RECOGNITION = True`
- Check console logs for errors

**Search download timeout:**
- File might be too large
- Check your internet connection
- Bot will show "Search on YouTube" button as fallback

### Update yt-dlp

**Via bot (admin only):**
```
/updateytdlp
```

**Manually:**
```bash
pip install --upgrade yt-dlp
# or use: ./update_ytdlp.sh (Linux/Mac)
# or use: update_ytdlp.bat (Windows)
```

## 📁 Project Structure

```
media-downloader-bot/
├── bot.py                   # Main bot code
├── config.py                # Configuration (create from config.example.py)
├── config.example.py        # Configuration template
├── database.py              # Database management
├── music_recognition.py     # Music recognition module
├── music_handlers.py        # Music recognition handlers
├── text_search.py           # Song search module
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── .gitignore               # Git ignore rules
├── start.sh                 # Linux/Mac startup script
├── start.bat                # Windows startup script
├── update_ytdlp.sh          # yt-dlp update script (Linux/Mac)
├── update_ytdlp.bat         # yt-dlp update script (Windows)
├── downloads/               # Temporary downloads (auto-created)
└── bot_data.json            # Database file (auto-created)
```

## 🔒 Security Notes

- ⚠️ **Never commit `config.py`** - It contains sensitive credentials
- ✅ Always use `config.example.py` as a template
- 🔐 Keep your bot token and API keys private
- 🧹 Bot automatically cleans up downloaded files
- 🚫 Admin commands are restricted to configured `ADMIN_ID`
- 💾 All data stored locally in `bot_data.json`

## 🚀 Deployment

### Local

```bash
python bot.py
```

### Background (Linux/Mac)

```bash
nohup python bot.py > bot.log 2>&1 &
```

### systemd Service (Linux)

Create `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Media Downloader Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/media-downloader-bot
ExecStart=/usr/bin/python3 /path/to/media-downloader-bot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

### Docker (Coming Soon)

```bash
docker build -t media-bot .
docker run -d --name media-bot media-bot
```

## 📊 Statistics

The bot tracks:
- Total downloads
- Downloads by platform (YouTube, Instagram, TikTok, etc.)
- Downloads by type (Video, Audio)
- User activity
- Top users
- Recent downloads

Access via `/admin` command.

## 🎯 Roadmap

- [x] Multi-platform download support
- [x] Music recognition (Shazam-like)
- [x] Text-based song search
- [x] Auto-download from search
- [ ] Playlist download support
- [ ] Direct music download (skip YouTube search)
- [ ] Spotify/Apple Music integration
- [ ] Docker deployment
- [ ] Web dashboard
- [ ] Multi-language support

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits

- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Downloads powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Music recognition by [ACRCloud](https://www.acrcloud.com/)
- Song search via [iTunes API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/)

## 💖 Support

If you find this project useful, please consider:
- ⭐ Starring the repository
- 🐛 Reporting bugs
- 💡 Suggesting new features
- 📢 Sharing with friends

## 📞 Contact

For issues or questions:
- Open an [Issue](https://github.com/yourusername/media-downloader-bot/issues)
- Contact the bot administrator

---

<div align="center">
Made with ❤️ for the Telegram community
</div>
