# Changelog

All notable changes to this project will be documented in this file.

## [2.3.0] - 2025-11-12

### 🚀 Added - 2GB File Support!
- **Large File Upload System** - Upload files up to 2GB (not just 50MB!)
  - Pyrogram Client API integration
  - Hybrid upload system (automatic method selection)
  - Files < 50MB → Bot API (fast)
  - Files 50MB-2GB → Client API (Pyrogram)
- **Smart Upload Logic** - Automatically chooses best method
- **Seamless Fallback** - Works without Client API (50MB limit)
- **GET_API_CREDENTIALS.md** - Step-by-step setup guide
- **Configuration Options** - ENABLE_LARGE_FILES, API_ID, API_HASH

### 🔧 Improved
- Updated requirements.txt with pyrogram and tgcrypto
- Enhanced file size checking and error messages
- Better upload progress indicators
- Documentation updated with 2GB support info

### 📚 Documentation
- Comprehensive guide for getting API credentials
- Updated README with 2GB feature
- Setup instructions for large file support

## [2.2.0] - 2025-11-12

### ✨ Added
- **Song Search Feature** - Text-based song search with auto-download
  - Search songs by name, artist, or lyrics
  - Powered by iTunes API (no key required)
  - Automatic YouTube search and download
  - Interactive button interface
  - Admin-only during testing phase
- **Music Recognition** - Shazam-like functionality
  - Identify songs from audio files or voice messages
  - ACRCloud audio fingerprinting integration
  - Instant song details (title, artist, album, year)
  - YouTube integration for found songs
  - Cover song detection

### 🔧 Improved
- **Upload Reliability**
  - Increased timeouts to 120 seconds
  - Smart retry logic (3 attempts)
  - Document fallback if audio upload fails
  - Better progress indicators
  - Network error detection
- **Audio Quality**
  - Prefer smaller file sizes (under 10MB)
  - Lower bitrate for faster uploads (128kbps)
  - Better format selection
  - FFmpeg auto-detection with fallback

### 📚 Documentation
- Comprehensive README with all features
- Detailed SETUP.md guide
- CONTRIBUTING.md for contributors
- LICENSE file (MIT)
- config.example.py template
- Better inline code comments

### 🔒 Security
- config.py now in .gitignore
- Sensitive credentials removed from repo
- config.example.py template provided
- Security notes in README

## [2.1.0] - Earlier

### 🔧 Platform Fixes
- **TikTok Improvements**
  - Added referer headers
  - Webpage download support
  - Better compatibility with share links
- **Facebook Improvements**
  - Multiple API fallback methods
  - Better error messages
  - Support for mobile and web links

### ⚡ Technical
- Retry mechanism (3 attempts)
- Platform-specific headers
- Simplified format selection
- Geo-bypass enabled
- Better error messages with troubleshooting tips

### 📖 Documentation
- TROUBLESHOOTING.md guide
- Platform-specific solutions
- Update scripts for yt-dlp

## [2.0.0] - Initial Release

### ✨ Features
- Multi-platform downloads (YouTube, Instagram, TikTok, Facebook, etc.)
- Multiple quality options (Best, 1080p, 720p, 480p, 360p)
- Audio extraction (MP3, M4A, OPUS)
- Admin panel with full dashboard
- User management (ban/unban)
- Statistics tracking
- Download history
- JSON database
- Automatic file cleanup

### 👑 Admin Features
- Interactive admin dashboard
- User activity monitoring
- Platform-wise statistics
- Top users leaderboard
- Recent downloads view
- Ban system

---

## Version Format

[MAJOR.MINOR.PATCH]

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

## Labels

- ✨ **Added**: New features
- 🔧 **Improved**: Enhancements
- 🐛 **Fixed**: Bug fixes
- 📚 **Documentation**: Docs updates
- 🔒 **Security**: Security improvements
- ⚡ **Technical**: Internal improvements
- 🗑️ **Deprecated**: Soon-to-be removed
- ❌ **Removed**: Removed features
