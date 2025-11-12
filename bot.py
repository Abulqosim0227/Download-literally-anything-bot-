#!/usr/bin/env python3
"""
Media Downloader Bot for Telegram
Supports: YouTube, Instagram, TikTok, Facebook, and more
"""

import os
import re
import logging
import asyncio
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import yt_dlp

from config import *
from database import Database

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create download directory
Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

# Initialize database
db = Database()


class MediaDownloader:
    """Handle media downloads from various platforms"""

    @staticmethod
    def get_base_options(url: str) -> dict:
        """Get platform-specific base options for yt-dlp"""
        options = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }

        # Platform-specific options
        url_lower = url.lower()

        if 'tiktok.com' in url_lower:
            options['http_headers'].update({
                'Referer': 'https://www.tiktok.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            })
            # TikTok specific
            options['extractor_args'] = {'tiktok': {'webpage_download': True}}

        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            options['http_headers'].update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cookie': '',  # Facebook works better without cookies sometimes
            })
            # Try multiple methods
            options['extractor_args'] = {'facebook': {'api': ['mobile', 'www']}}

        elif 'instagram.com' in url_lower:
            options['http_headers'].update({
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            })

        return options

    @staticmethod
    def get_video_info(url: str) -> tuple[Optional[dict], Optional[str]]:
        """Get video information without downloading

        Returns:
            tuple: (info_dict, error_message)
        """
        ydl_opts = MediaDownloader.get_base_options(url)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info, None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error getting video info for {url}: {error_msg}")

            # Provide specific error messages based on platform and error type
            if "cannot parse data" in error_msg.lower():
                return None, "❌ Cannot parse this video. The platform may have updated their system.\n\n💡 Try:\n• Update the bot: pip install --upgrade yt-dlp\n• Try a different video from the same platform\n• Report to admin if issue persists"

            elif "tiktok" in url.lower() and ("redirect" in error_msg.lower() or "extract" in error_msg.lower()):
                return None, "❌ TikTok download failed.\n\n💡 Try:\n• Make sure the video is public\n• Copy the link directly from TikTok app\n• Use the share button and 'Copy link'\n• Avoid shortened links"

            elif "facebook" in url.lower() or "fb.watch" in url.lower():
                return None, "❌ Facebook download failed.\n\n💡 Try:\n• Make sure the video is PUBLIC (not friends-only)\n• Use the full facebook.com URL (not fb.watch)\n• Right-click video → 'Copy video URL'\n• Some Facebook videos cannot be downloaded due to privacy settings"

            elif "inappropriate" in error_msg.lower() or "unavailable for certain audiences" in error_msg.lower():
                return None, "❌ This content is age-restricted or private.\n\n💡 Try:\n• Public posts only\n• Non-age-restricted content"

            elif "private" in error_msg.lower():
                return None, "❌ This content is private and cannot be downloaded."

            elif "login" in error_msg.lower() or "sign in" in error_msg.lower():
                return None, "❌ This content requires login.\n\n💡 Try:\n• Use a public post\n• Check if video is available to everyone"

            elif "not found" in error_msg.lower() or "404" in error_msg:
                return None, "❌ Content not found. The video may have been deleted or the link is incorrect."

            elif "geo" in error_msg.lower() or "region" in error_msg.lower():
                return None, "❌ This video is geo-restricted (not available in your region)."

            else:
                # Generic error with platform detection
                platform = detect_platform(url)
                return None, f"❌ Could not retrieve video from {platform}.\n\n🔧 Error: {error_msg[:150]}\n\n💡 Troubleshooting:\n• Make sure video is public\n• Check if URL is correct\n• Try updating: pip install --upgrade yt-dlp\n• Report to admin if issue persists"

    @staticmethod
    async def download_video(url: str, quality: str, output_path: str) -> Optional[str]:
        """Download video with specified quality"""

        # Get base options for platform
        ydl_opts = MediaDownloader.get_base_options(url)

        # Quality format selection - relaxed for problematic platforms
        url_lower = url.lower()
        is_problematic = 'tiktok.com' in url_lower or 'facebook.com' in url_lower or 'fb.watch' in url_lower

        if is_problematic:
            # For TikTok and Facebook, use simpler format selection
            if quality == "best":
                format_spec = "best"
            else:
                # Try to get specific quality but fallback to best
                format_spec = f"best[height<={quality[:-1]}]/best"
        else:
            # For other platforms, use more specific format selection
            if quality == "best":
                format_spec = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            elif quality == "1080p":
                format_spec = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"
            elif quality == "720p":
                format_spec = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
            elif quality == "480p":
                format_spec = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best"
            else:  # 360p
                format_spec = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best"

        # Update options for download
        ydl_opts.update({
            'format': format_spec,
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
            'retries': 3,
            'fragment_retries': 3,
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                return output_path
        except Exception as e:
            logger.error(f"Error downloading video from {url}: {e}")
            return None

    @staticmethod
    async def download_audio(url: str, audio_format: str, output_path: str) -> Optional[str]:
        """Download and extract audio"""

        # Get base options for platform
        ydl_opts = MediaDownloader.get_base_options(url)

        # Update options for audio download
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': '192',
            }],
            'quiet': False,
            'retries': 3,
            'fragment_retries': 3,
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                # yt-dlp adds the extension automatically
                audio_file = output_path.rsplit('.', 1)[0] + f'.{audio_format}'
                return audio_file
        except Exception as e:
            logger.error(f"Error downloading audio from {url}: {e}")
            return None


def is_url(text: str) -> bool:
    """Check if text contains a URL"""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.search(text))


def detect_platform(url: str) -> str:
    """Detect platform from URL"""
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YouTube'
    elif 'instagram.com' in url_lower:
        return 'Instagram'
    elif 'tiktok.com' in url_lower:
        return 'TikTok'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'Facebook'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'Twitter/X'
    elif 'reddit.com' in url_lower:
        return 'Reddit'
    elif 'vimeo.com' in url_lower:
        return 'Vimeo'
    else:
        return 'Other'


async def check_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is banned"""
    user_id = update.effective_user.id

    if db.is_banned(user_id):
        await update.message.reply_text(
            "🚫 You have been banned from using this bot.\n\n"
            "If you believe this is a mistake, please contact the admin."
        )
        return True
    return False


async def track_user(update: Update):
    """Track user activity"""
    user = update.effective_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message"""
    # Track user
    await track_user(update)

    # Check if banned
    if await check_ban(update, context):
        return

    user = update.effective_user
    user_data = db.get_user(user.id)

    # Create keyboard with quick actions
    keyboard = [
        [
            InlineKeyboardButton("📹 YouTube", url="https://youtube.com"),
            InlineKeyboardButton("📸 Instagram", url="https://instagram.com"),
        ],
        [
            InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com"),
            InlineKeyboardButton("📘 Facebook", url="https://facebook.com"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="show_help"),
            InlineKeyboardButton("📊 My Stats", callback_data="my_stats"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = f"""👋 Welcome back, {user.first_name}!

🎬 Media Downloader Bot

I can download videos and audio from:
📹 YouTube • 📸 Instagram • 🎵 TikTok
📘 Facebook • 🐦 Twitter/X • 📱 Reddit
🎥 Vimeo • And many more!

━━━━━━━━━━━━━━━━━
📝 How to use:
1️⃣ Send me a link to any video
2️⃣ Choose video quality or audio format
3️⃣ Get your media instantly!

💡 Features:
✨ Multiple quality options (360p - 1080p)
🎵 Audio extraction (MP3, M4A, OPUS)
⚡ Fast and reliable downloads
🔒 Secure and private

━━━━━━━━━━━━━━━━━
📊 Your Stats: {user_data['total_downloads'] if user_data else 0} downloads

Just send me a link to get started! 🚀"""

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming URLs"""
    # Track user
    await track_user(update)

    # Check if banned
    if await check_ban(update, context):
        return

    url = update.message.text.strip()

    if not is_url(url):
        await update.message.reply_text("❌ Please send a valid URL!")
        return

    # Detect platform
    platform = detect_platform(url)

    # Send processing message
    processing_msg = await update.message.reply_text(f"🔍 Analyzing the link from {platform}...")

    # Get video info
    info, error = MediaDownloader.get_video_info(url)

    if not info:
        error_message = error if error else "❌ Could not retrieve video information. Please check the URL and try again."
        await processing_msg.edit_text(error_message)
        return

    # Store URL in user data
    context.user_data['url'] = url
    context.user_data['platform'] = platform
    context.user_data['title'] = info.get('title', 'Unknown')
    context.user_data['duration'] = info.get('duration', 0)
    context.user_data['uploader'] = info.get('uploader', 'Unknown')

    # Create keyboard with options
    keyboard = [
        [
            InlineKeyboardButton("🎥 Video (Best)", callback_data="video_best"),
            InlineKeyboardButton("🎥 1080p", callback_data="video_1080p"),
        ],
        [
            InlineKeyboardButton("🎥 720p", callback_data="video_720p"),
            InlineKeyboardButton("🎥 480p", callback_data="video_480p"),
        ],
        [
            InlineKeyboardButton("🎥 360p", callback_data="video_360p"),
        ],
        [
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data="audio_mp3"),
            InlineKeyboardButton("🎵 Audio (M4A)", callback_data="audio_m4a"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Format duration
    duration = info.get('duration', 0)
    if duration:
        duration = int(duration)  # Convert to int to avoid formatting errors
        minutes = duration // 60
        seconds = duration % 60
        duration_str = f"{minutes}:{seconds:02d}"
    else:
        duration_str = "Unknown"

    # Escape special characters for clean display
    title = info.get('title', 'Unknown')[:100]
    uploader = info.get('uploader', 'Unknown')

    info_text = f"""✅ Video Found!

📺 Title: {title}
👤 Uploader: {uploader}
⏱ Duration: {duration_str}

📥 Select download option:"""

    await processing_msg.edit_text(info_text, reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()

    # Handle special callbacks
    if query.data == "show_help":
        await show_help_inline(query)
        return
    elif query.data == "my_stats":
        await show_user_stats(query)
        return
    elif query.data == "back_to_start":
        # Recreate start message
        user = query.from_user
        user_data = db.get_user(user.id)

        keyboard = [
            [
                InlineKeyboardButton("📹 YouTube", url="https://youtube.com"),
                InlineKeyboardButton("📸 Instagram", url="https://instagram.com"),
            ],
            [
                InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com"),
                InlineKeyboardButton("📘 Facebook", url="https://facebook.com"),
            ],
            [
                InlineKeyboardButton("ℹ️ Help", callback_data="show_help"),
                InlineKeyboardButton("📊 My Stats", callback_data="my_stats"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_message = f"""👋 Welcome back, {user.first_name}!

🎬 Media Downloader Bot

I can download videos and audio from:
📹 YouTube • 📸 Instagram • 🎵 TikTok
📘 Facebook • 🐦 Twitter/X • 📱 Reddit
🎥 Vimeo • And many more!

━━━━━━━━━━━━━━━━━
📝 How to use:
1️⃣ Send me a link to any video
2️⃣ Choose video quality or audio format
3️⃣ Get your media instantly!

💡 Features:
✨ Multiple quality options (360p - 1080p)
🎵 Audio extraction (MP3, M4A, OPUS)
⚡ Fast and reliable downloads
🔒 Secure and private

━━━━━━━━━━━━━━━━━
📊 Your Stats: {user_data['total_downloads'] if user_data else 0} downloads

Just send me a link to get started! 🚀"""

        await query.edit_message_text(welcome_message, reply_markup=reply_markup)
        return
    elif query.data.startswith("admin_"):
        action = query.data.replace("admin_", "")
        await admin_callback(query, action)
        return
    elif query.data.startswith("search_"):
        # Handle search callbacks (admin only)
        if query.from_user.id != ADMIN_ID:
            await query.answer("❌ Admin only!", show_alert=True)
            return

        if query.data == "search_cancel":
            await query.edit_message_text("❌ Search cancelled.")
            return
        elif query.data == "search_back":
            # Show search results again
            results = context.user_data.get('search_results', [])
            if not results:
                await query.edit_message_text("❌ Search results expired. Use /search again.")
                return

            from text_search import song_searcher
            results_text = song_searcher.format_results(results)

            keyboard = []
            for i, song in enumerate(results[:5], 1):
                title = song.get('title', 'Unknown')[:30]
                artist = song.get('artist', 'Unknown')[:20]
                button_text = f"{i}. {title} - {artist}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"search_select_{i-1}")])

            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"{results_text}\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"Select a song to download:",
                reply_markup=reply_markup
            )
            return
        elif query.data.startswith("search_select_"):
            result_index = int(query.data.split("_")[-1])
            await handle_search_callback(query, context, result_index)
            return
        elif query.data.startswith("search_copy_"):
            result_index = int(query.data.split("_")[-1])
            results = context.user_data.get('search_results', [])
            if results and result_index < len(results):
                song = results[result_index]
                copy_text = f"{song.get('artist', 'Unknown')} - {song.get('title', 'Unknown')}"
                await query.answer(f"Copied: {copy_text}", show_alert=True)
            return

    # Get stored URL
    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ Session expired. Please send the link again.")
        return

    # Parse callback data
    action, option = query.data.split('_')

    # Update message
    await query.edit_message_text(f"⏬ Downloading... Please wait.")

    # Generate output filename
    title = context.user_data.get('title', 'video').replace('/', '_').replace('\\', '_')
    safe_title = re.sub(r'[^\w\s-]', '', title)[:50]

    if action == "video":
        output_file = os.path.join(DOWNLOAD_DIR, f"{safe_title}_{option}.mp4")

        # Download video
        result = await MediaDownloader.download_video(url, option, output_file)

        if result and os.path.exists(result):
            file_size = os.path.getsize(result)

            # Check if we need large file uploader
            try:
                from large_file_uploader import large_file_uploader, is_large_file_enabled
                from config import BOT_API_LIMIT
            except ImportError:
                BOT_API_LIMIT = 50 * 1024 * 1024

            # Check file size
            if file_size > MAX_FILE_SIZE:
                await query.edit_message_text(
                    f"❌ File is too large ({file_size / 1024 / 1024:.1f} MB). "
                    f"Maximum size: {MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB."
                )
                os.remove(result)
                return

            # Send video (choose method based on file size)
            file_size_mb = file_size / 1024 / 1024

            # Use Client API for files >= 50MB if available
            if file_size >= BOT_API_LIMIT and is_large_file_enabled():
                await query.edit_message_text(
                    f"📤 Uploading large video ({file_size_mb:.1f} MB)...\n"
                    f"Using Client API for files over 50MB"
                )

                try:
                    success = await large_file_uploader.upload_video(
                        chat_id=query.message.chat_id,
                        file_path=result,
                        caption=f"🎬 {context.user_data.get('title', 'Video')[:100]}\n\n📥 Quality: {option}\n📁 Size: {file_size_mb:.1f} MB"
                    )

                    if success:
                        # Record download
                        db.record_download(
                            user_id=query.from_user.id,
                            download_type="video",
                            platform=context.user_data.get('platform', 'unknown'),
                            url=url
                        )
                        await query.edit_message_text("✅ Large video sent successfully! 🎉")
                    else:
                        await query.edit_message_text("❌ Failed to upload video. Try a lower quality.")
                except Exception as e:
                    logger.error(f"Error sending large video: {e}")
                    await query.edit_message_text(f"❌ Error uploading large video: {str(e)}")
            else:
                # Use Bot API for files < 50MB
                await query.edit_message_text(f"📤 Uploading video ({file_size_mb:.1f} MB)...")

                try:
                    with open(result, 'rb') as video:
                        await context.bot.send_video(
                            chat_id=query.message.chat_id,
                            video=video,
                            caption=f"🎬 {context.user_data.get('title', 'Video')[:100]}\n\n📥 Quality: {option}",
                            supports_streaming=True
                        )

                    # Record download in database
                    db.record_download(
                        user_id=query.from_user.id,
                        download_type="video",
                        platform=context.user_data.get('platform', 'unknown'),
                        url=url
                    )

                    await query.edit_message_text("✅ Video sent successfully! 🎉")
                except Exception as e:
                    logger.error(f"Error sending video: {e}")
                    await query.edit_message_text(f"❌ Error sending video: {str(e)}")

            # Clean up
            try:
                if os.path.exists(result):
                    os.remove(result)
            except:
                pass
        else:
            await query.edit_message_text("❌ Download failed. Please try again or use a different quality.")

    elif action == "audio":
        output_file = os.path.join(DOWNLOAD_DIR, f"{safe_title}.{option}")

        # Download audio
        result = await MediaDownloader.download_audio(url, option, output_file)

        if result and os.path.exists(result):
            file_size = os.path.getsize(result)

            # Check if we need large file uploader
            try:
                from large_file_uploader import large_file_uploader, is_large_file_enabled
                from config import BOT_API_LIMIT
            except ImportError:
                BOT_API_LIMIT = 50 * 1024 * 1024

            # Check file size
            if file_size > MAX_FILE_SIZE:
                await query.edit_message_text(
                    f"❌ File is too large ({file_size / 1024 / 1024:.1f} MB). "
                    f"Maximum size: {MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB."
                )
                os.remove(result)
                return

            # Send audio (choose method based on file size)
            file_size_mb = file_size / 1024 / 1024

            # Use Client API for files >= 50MB if available
            if file_size >= BOT_API_LIMIT and is_large_file_enabled():
                await query.edit_message_text(
                    f"📤 Uploading large audio ({file_size_mb:.1f} MB)...\n"
                    f"Using Client API for files over 50MB"
                )

                try:
                    success = await large_file_uploader.upload_audio(
                        chat_id=query.message.chat_id,
                        file_path=result,
                        title=context.user_data.get('title', 'Audio'),
                        caption=f"🎵 {context.user_data.get('title', 'Audio')[:100]}\n\n📥 Format: {option.upper()}\n📁 Size: {file_size_mb:.1f} MB"
                    )

                    if success:
                        # Record download
                        db.record_download(
                            user_id=query.from_user.id,
                            download_type="audio",
                            platform=context.user_data.get('platform', 'unknown'),
                            url=url
                        )
                        await query.edit_message_text("✅ Large audio sent successfully! 🎉")
                    else:
                        await query.edit_message_text("❌ Failed to upload audio.")
                except Exception as e:
                    logger.error(f"Error sending large audio: {e}")
                    await query.edit_message_text(f"❌ Error uploading large audio: {str(e)}")
            else:
                # Use Bot API for files < 50MB
                await query.edit_message_text(f"📤 Uploading audio ({file_size_mb:.1f} MB)...")

                try:
                    with open(result, 'rb') as audio:
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=audio,
                            caption=f"🎵 {context.user_data.get('title', 'Audio')[:100]}\n\n📥 Format: {option.upper()}",
                            title=context.user_data.get('title', 'Audio')
                        )

                    # Record download in database
                    db.record_download(
                        user_id=query.from_user.id,
                        download_type="audio",
                        platform=context.user_data.get('platform', 'unknown'),
                        url=url
                    )

                    await query.edit_message_text("✅ Audio sent successfully! 🎉")
                except Exception as e:
                    logger.error(f"Error sending audio: {e}")
                    await query.edit_message_text(f"❌ Error sending audio: {str(e)}")

            # Clean up
            try:
                if os.path.exists(result):
                    os.remove(result)
            except:
                pass
        else:
            await query.edit_message_text("❌ Download failed. Please try again.")


async def show_help_inline(query):
    """Show help message inline"""
    help_text = """ℹ️ Help & Instructions

How to download:
1️⃣ Copy a video link from any supported platform
2️⃣ Send the link to me
3️⃣ Choose your preferred quality or format
4️⃣ Wait for the download and upload

Supported platforms:
📹 YouTube (videos, shorts, playlists)
📸 Instagram (posts, reels, IGTV)
🎵 TikTok
📘 Facebook
🐦 Twitter/X
📱 Reddit
🎥 Vimeo
✨ And many more!

Available formats:
📹 Video: Best, 1080p, 720p, 480p, 360p
🎵 Audio: MP3, M4A, OPUS

Commands:
/start - Start the bot
/help - Show this message
/admin - Admin panel (admin only)

Note: Maximum file size is 50 MB due to Telegram limitations."""

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(help_text, reply_markup=reply_markup)


async def show_user_stats(query):
    """Show user statistics inline"""
    user_id = query.from_user.id
    user_data = db.get_user(user_id)

    if not user_data:
        await query.edit_message_text("❌ No statistics available yet. Start downloading!")
        return

    stats_text = f"""📊 Your Statistics

👤 Username: @{user_data.get('username', 'N/A')}
🆔 User ID: {user_id}

━━━━━━━━━━━━━━━━━
📥 Download Stats:
• Total Downloads: {user_data['total_downloads']}
• Video Downloads: {user_data['video_downloads']}
• Audio Downloads: {user_data['audio_downloads']}

📅 First seen: {user_data.get('first_seen', 'Unknown')[:10]}
🕒 Last active: {user_data.get('last_seen', 'Unknown')[:10]}

Keep downloading! 🚀"""

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(stats_text, reply_markup=reply_markup)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    stats = db.get_statistics()

    keyboard = [
        [
            InlineKeyboardButton("👥 View Users", callback_data="admin_users"),
            InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("🚫 Banned Users", callback_data="admin_banned"),
            InlineKeyboardButton("📈 Top Users", callback_data="admin_top"),
        ],
        [
            InlineKeyboardButton("📜 Recent Downloads", callback_data="admin_recent"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    admin_text = f"""🔐 Admin Panel

━━━━━━━━━━━━━━━━━
📊 Quick Stats:
👥 Total Users: {stats['total_users']}
📥 Total Downloads: {stats['total_downloads']}
🎥 Video Downloads: {stats['video_downloads']}
🎵 Audio Downloads: {stats['audio_downloads']}
🚫 Banned Users: {len(db.get_banned_users())}

━━━━━━━━━━━━━━━━━
Select an option below:"""

    await update.message.reply_text(admin_text, reply_markup=reply_markup)


async def admin_callback(query, action: str):
    """Handle admin panel callbacks"""
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    if action == "users":
        users = db.get_all_users()
        total = len(users)

        users_text = f"""👥 All Users ({total})

"""
        for i, user in enumerate(users[:20], 1):
            username = user.get('username', 'No username')
            first_name = user.get('first_name', 'Unknown')
            downloads = user.get('total_downloads', 0)
            users_text += f"{i}. @{username} - {first_name}\n   ID: {user['user_id']} | Downloads: {downloads}\n\n"

        if total > 20:
            users_text += f"\n... and {total - 20} more users"

        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")],
            [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban_prompt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(users_text[:4000], reply_markup=reply_markup)

    elif action == "stats":
        stats = db.get_statistics()
        platform_stats = stats.get('platform_stats', {})

        stats_text = f"""📊 Detailed Statistics

━━━━━━━━━━━━━━━━━
👥 Users: {stats['total_users']}
📥 Total Downloads: {stats['total_downloads']}
🎥 Videos: {stats['video_downloads']}
🎵 Audio: {stats['audio_downloads']}

🌐 Platform Statistics:
"""
        for platform, count in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True):
            stats_text += f"• {platform}: {count}\n"

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(stats_text, reply_markup=reply_markup)

    elif action == "banned":
        banned_ids = db.get_banned_users()

        if not banned_ids:
            banned_text = "🚫 No banned users"
        else:
            banned_text = f"🚫 Banned Users ({len(banned_ids)})\n\n"
            for user_id in banned_ids:
                user_data = db.get_user(user_id)
                if user_data:
                    username = user_data.get('username', 'No username')
                    banned_text += f"• @{username} (ID: {user_id})\n"
                else:
                    banned_text += f"• ID: {user_id}\n"

        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")],
            [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban_prompt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(banned_text, reply_markup=reply_markup)

    elif action == "top":
        top_users = db.get_top_users(10)

        top_text = "📈 Top 10 Users\n\n"
        for i, user in enumerate(top_users, 1):
            username = user.get('username', 'No username')
            first_name = user.get('first_name', 'Unknown')
            downloads = user.get('total_downloads', 0)
            top_text += f"{i}. @{username} - {first_name}\n   Downloads: {downloads} (🎥 {user.get('video_downloads', 0)} | 🎵 {user.get('audio_downloads', 0)})\n\n"

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(top_text, reply_markup=reply_markup)

    elif action == "recent":
        recent = db.get_recent_downloads(10)

        if not recent:
            recent_text = "📜 No recent downloads"
        else:
            recent_text = "📜 Recent Downloads\n\n"
            for download in recent:
                user_id = download.get('user_id')
                user_data = db.get_user(user_id)
                username = user_data.get('username', 'Unknown') if user_data else 'Unknown'
                dtype = download.get('type', 'unknown')
                platform = download.get('platform', 'unknown')
                timestamp = download.get('timestamp', '')[:16]

                recent_text += f"• @{username} - {dtype} from {platform}\n  {timestamp}\n\n"

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(recent_text[:4000], reply_markup=reply_markup)

    elif action == "panel":
        stats = db.get_statistics()

        keyboard = [
            [
                InlineKeyboardButton("👥 View Users", callback_data="admin_users"),
                InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton("🚫 Banned Users", callback_data="admin_banned"),
                InlineKeyboardButton("📈 Top Users", callback_data="admin_top"),
            ],
            [
                InlineKeyboardButton("📜 Recent Downloads", callback_data="admin_recent"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        admin_text = f"""🔐 Admin Panel

━━━━━━━━━━━━━━━━━
📊 Quick Stats:
👥 Total Users: {stats['total_users']}
📥 Total Downloads: {stats['total_downloads']}
🎥 Video Downloads: {stats['video_downloads']}
🎵 Audio Downloads: {stats['audio_downloads']}
🚫 Banned Users: {len(db.get_banned_users())}

━━━━━━━━━━━━━━━━━
Select an option below:"""

        await query.edit_message_text(admin_text, reply_markup=reply_markup)


async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        user_id = int(context.args[0])
        db.ban_user(user_id)
        user_data = db.get_user(user_id)
        username = user_data.get('username', 'Unknown') if user_data else 'Unknown'
        await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) has been banned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")


async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a user (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        user_id = int(context.args[0])
        db.unban_user(user_id)
        user_data = db.get_user(user_id)
        username = user_data.get('username', 'Unknown') if user_data else 'Unknown'
        await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) has been unbanned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")


async def update_ytdlp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update yt-dlp to latest version (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    await update.message.reply_text("🔄 Updating yt-dlp... Please wait.")

    try:
        import subprocess
        result = subprocess.run(
            ["pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            # Get new version
            version_result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True
            )
            version = version_result.stdout.strip() if version_result.returncode == 0 else "Unknown"

            await update.message.reply_text(
                f"✅ yt-dlp updated successfully!\n\n"
                f"📦 Version: {version}\n\n"
                f"💡 Tip: Restart bot for best results"
            )
        else:
            await update.message.reply_text(
                f"❌ Update failed.\n\n"
                f"Error: {result.stderr[:200]}"
            )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Update timed out. Try again later.")
    except Exception as e:
        await update.message.reply_text(f"❌ Update failed: {str(e)}")


async def check_version(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check yt-dlp version (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    try:
        import subprocess
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            await update.message.reply_text(
                f"📦 yt-dlp Version Info\n\n"
                f"Current: {version}\n\n"
                f"💡 Update with: /updateytdlp"
            )
        else:
            await update.message.reply_text("❌ Could not check version.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    # Get basic stats
    stats_text = f"""📊 Bot Statistics

👤 Admin ID: {ADMIN_ID}
📁 Download Directory: {DOWNLOAD_DIR}
💾 Max File Size: {MAX_FILE_SIZE / 1024 / 1024} MB

🌐 Supported Platforms:
{chr(10).join(f"• {platform}" for platform in SUPPORTED_PLATFORMS)}"""

    await update.message.reply_text(stats_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message"""
    help_text = """ℹ️ Help & Instructions

How to download:
1. Copy a video link from any supported platform
2. Send the link to me
3. Choose your preferred quality or format
4. Wait for the download and upload

Supported platforms:
• YouTube (videos, shorts, playlists)
• Instagram (posts, reels, IGTV)
• TikTok
• Facebook
• Twitter/X
• Reddit
• Vimeo
• And many more!

Available formats:
📹 Video: Best, 1080p, 720p, 480p, 360p
🎵 Audio: MP3, M4A, OPUS

Commands:
/start - Start the bot
/help - Show this message
/stats - Bot statistics (admin only)

Note: Maximum file size is 50 MB due to Telegram limitations. If a video is too large, try a lower quality.

Need support? Contact the admin."""

    await update.message.reply_text(help_text)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search for songs by text (ADMIN ONLY - Testing Phase)
    Usage: /search <song name or artist>
    """
    # ADMIN ONLY for testing
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is currently in testing (admin only).")
        return

    try:
        # Check if text search is available
        try:
            from text_search import song_searcher, is_enabled as search_is_enabled
        except ImportError as e:
            logger.error(f"Text search import error: {e}")
            await update.message.reply_text(f"❌ Text search module not available.\nError: {str(e)[:100]}")
            return

        if not search_is_enabled():
            await update.message.reply_text("❌ Text search is not initialized. Check logs for details.")
            return

        # Get search query
        if not context.args:
            await update.message.reply_text(
                "🔍 Song Search (Admin Testing)\n\n"
                "Usage: /search <query>\n\n"
                "Examples:\n"
                "• /search Blinding Lights\n"
                "• /search The Weeknd\n"
                "• /search shape of you ed sheeran"
            )
            return

        query = " ".join(context.args)
        logger.info(f"Search query: '{query}'")

        # Send searching message
        searching_msg = await update.message.reply_text(f"🔍 Searching for: '{query}'...")

        # Perform search
        success, results, error = song_searcher.search_songs(query, limit=5)

        if not success or not results:
            error_msg = error or "No results found."
            logger.warning(f"Search failed for '{query}': {error_msg}")
            await searching_msg.edit_text(f"❌ {error_msg}")
            return

        logger.info(f"Found {len(results)} results for '{query}'")

        # Format results
        results_text = song_searcher.format_results(results)

        # Create buttons for each result
        keyboard = []
        for i, song in enumerate(results[:5], 1):
            title = song.get('title', 'Unknown')[:30]
            artist = song.get('artist', 'Unknown')[:20]
            button_text = f"{i}. {title} - {artist}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"search_select_{i-1}")])

        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Store results in context for later
        context.user_data['search_results'] = results
        context.user_data['search_query'] = query

        await searching_msg.edit_text(
            f"{results_text}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"Select a song to download:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Search command error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Search error: {str(e)[:150]}\n\n"
            f"Please check the logs for details."
        )


async def handle_search_callback(query, context, result_index: int):
    """Handle selection from search results (admin only) - Auto-download from YouTube"""
    results = context.user_data.get('search_results', [])

    if not results or result_index >= len(results):
        await query.edit_message_text("❌ Search results expired. Please search again.")
        return

    song = results[result_index]
    title = song.get('title', 'Unknown')
    artist = song.get('artist', 'Unknown')

    # Show searching message
    await query.edit_message_text(
        f"🔍 Searching YouTube for:\n\n"
        f"🎵 {title}\n"
        f"🎤 {artist}\n\n"
        f"⏳ Please wait..."
    )

    try:
        # Search YouTube using yt-dlp
        search_query = f"{artist} {title} official audio"
        search_url = f"ytsearch1:{search_query}"

        logger.info(f"Searching YouTube: {search_query}")

        # Get video info
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'no_color': True}) as ydl:
            info = ydl.extract_info(search_url, download=False)
            if 'entries' in info and len(info['entries']) > 0:
                video_info = info['entries'][0]
                video_url = video_info.get('webpage_url') or video_info.get('url')
                video_title = video_info.get('title', title)

                logger.info(f"Found YouTube video: {video_url}")

                # Update message
                await query.edit_message_text(
                    f"✅ Found on YouTube:\n\n"
                    f"🎵 {video_title}\n\n"
                    f"⏬ Downloading audio... Please wait."
                )

                # Download audio using simpler method
                safe_filename = re.sub(r'[^\w\s-]', '', f"{artist}_{title}")[:50]
                output_template = os.path.join(DOWNLOAD_DIR, safe_filename)

                # Check if FFmpeg is available
                ffmpeg_available = False
                try:
                    import subprocess
                    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                    ffmpeg_available = True
                    logger.info("FFmpeg is available")
                except:
                    logger.warning("FFmpeg not found - downloading without conversion")

                # Download with yt-dlp - use lower quality for smaller file size
                if ffmpeg_available:
                    # With FFmpeg: Convert to MP3 with lower bitrate for smaller files
                    ydl_opts = {
                        'format': 'bestaudio[filesize<10M]/bestaudio/best',
                        'outtmpl': output_template + '.%(ext)s',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '128',  # Lower quality = smaller file
                        }],
                        'quiet': True,
                        'no_warnings': True,
                        'no_color': True,
                    }
                    expected_ext = '.mp3'
                else:
                    # Without FFmpeg: Download in original format, prefer smaller files
                    ydl_opts = {
                        'format': 'bestaudio[filesize<10M][ext=m4a]/bestaudio[ext=m4a]/bestaudio/best',
                        'outtmpl': output_template + '.%(ext)s',
                        'quiet': True,
                        'no_warnings': True,
                        'no_color': True,
                    }
                    expected_ext = None  # Will search for any audio file

                logger.info(f"Downloading to: {output_template}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    download_result = ydl.download([video_url])

                # Find the downloaded file
                result_file = None
                if expected_ext:
                    # Look for specific extension
                    if os.path.exists(output_template + expected_ext):
                        result_file = output_template + expected_ext

                if not result_file:
                    # Search for any audio file with the safe_filename
                    for file in os.listdir(DOWNLOAD_DIR):
                        if file.startswith(safe_filename) and (file.endswith('.mp3') or file.endswith('.m4a') or file.endswith('.webm') or file.endswith('.opus')):
                            result_file = os.path.join(DOWNLOAD_DIR, file)
                            logger.info(f"Found downloaded file: {result_file}")
                            break

                logger.info(f"Looking for file: {result_file}")

                if os.path.exists(result_file):
                    file_size = os.path.getsize(result_file)
                    logger.info(f"File found, size: {file_size} bytes")

                    if file_size > MAX_FILE_SIZE:
                        await query.edit_message_text(
                            f"❌ File too large ({file_size / 1024 / 1024:.1f} MB)\n"
                            f"Maximum size: {MAX_FILE_SIZE / 1024 / 1024} MB\n\n"
                            f"Try searching on YouTube manually:\n{video_url}"
                        )
                        try:
                            os.remove(result_file)
                        except:
                            pass
                        return

                    # Update message with upload progress
                    await query.edit_message_text(
                        f"📤 Uploading audio...\n\n"
                        f"🎵 {title}\n"
                        f"🎤 {artist}\n"
                        f"📁 Size: {file_size / 1024 / 1024:.2f} MB\n\n"
                        f"Please wait..."
                    )

                    # Send audio file with retry logic and document fallback
                    upload_success = False
                    sent_as_document = False

                    for attempt in range(2):
                        try:
                            with open(result_file, 'rb') as audio_file:
                                await query.message.reply_audio(
                                    audio=audio_file,
                                    title=title,
                                    performer=artist,
                                    caption=f"🎵 {title}\n🎤 {artist}",
                                    read_timeout=120,
                                    write_timeout=120
                                )
                            upload_success = True
                            break
                        except Exception as upload_error:
                            logger.warning(f"Audio upload attempt {attempt + 1} failed: {upload_error}")
                            if attempt < 1:
                                await asyncio.sleep(2)

                    # If audio upload failed, try sending as document
                    if not upload_success:
                        logger.info("Trying to send as document instead")
                        try:
                            await query.edit_message_text(
                                f"⚠️ Audio upload failed. Trying alternative method...\n\n"
                                f"🎵 {title}\n"
                                f"🎤 {artist}"
                            )
                            with open(result_file, 'rb') as doc_file:
                                await query.message.reply_document(
                                    document=doc_file,
                                    filename=f"{artist} - {title}.mp3" if result_file.endswith('.mp3') else os.path.basename(result_file),
                                    caption=f"🎵 {title}\n🎤 {artist}",
                                    read_timeout=120,
                                    write_timeout=120
                                )
                            upload_success = True
                            sent_as_document = True
                        except Exception as doc_error:
                            logger.error(f"Document upload also failed: {doc_error}")
                            raise doc_error

                    if upload_success:
                        success_msg = f"✅ Downloaded successfully!\n\n"
                        success_msg += f"🎵 {title}\n"
                        success_msg += f"🎤 {artist}\n\n"
                        success_msg += f"📁 Size: {file_size / 1024 / 1024:.2f} MB"
                        if sent_as_document:
                            success_msg += f"\n\n💡 Sent as file (audio upload had issues)"

                        await query.edit_message_text(success_msg)

                        # Clean up
                        try:
                            os.remove(result_file)
                        except:
                            pass

                        # Record download
                        try:
                            db = Database()
                            db.record_download(query.from_user.id, 'audio', 'youtube_search', video_url)
                        except:
                            pass

                else:
                    logger.error(f"Downloaded file not found at: {result_file}")
                    raise Exception(f"Downloaded file not found at expected location")
            else:
                raise Exception("No results found on YouTube")

    except Exception as e:
        logger.error(f"Search download error: {e}", exc_info=True)

        # Generate YouTube search URL as fallback
        try:
            from text_search import song_searcher
            youtube_search_url = song_searcher.get_youtube_search_url(title, artist)
        except:
            youtube_search_url = f"https://www.youtube.com/results?search_query={artist}+{title}"

        keyboard = [
            [InlineKeyboardButton("🔍 Search on YouTube", url=youtube_search_url)],
            [InlineKeyboardButton("🔙 Back to Results", callback_data="search_back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        error_msg = str(e)
        error_type = type(e).__name__

        if "ffmpeg" in error_msg.lower() or "postprocessor" in error_msg.lower():
            error_detail = "FFmpeg not found. Install FFmpeg to enable audio conversion."
        elif "readerror" in error_type.lower() or "readtimeout" in error_type.lower():
            error_detail = "Connection interrupted during upload. Check your internet connection."
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            error_detail = "Upload timed out (file might be too large or connection is slow)"
        elif "httpx" in error_msg.lower() and ("error" in error_msg.lower() or "failed" in error_msg.lower()):
            error_detail = "Network error during upload. Please check your internet connection."
        else:
            error_detail = error_msg[:100]

        logger.error(f"Search download failed - Type: {error_type}, Message: {error_msg}")

        await query.edit_message_text(
            f"❌ Auto-download failed: {error_detail}\n\n"
            f"🎵 {title}\n"
            f"🎤 {artist}\n\n"
            f"Please try:\n"
            f"1. Click 'Search on YouTube' above\n"
            f"2. Copy the video URL\n"
            f"3. Send it to me",
            reply_markup=reply_markup
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors"""
    logger.error(f"Exception while handling an update: {context.error}")

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again later."
        )


def main() -> None:
    """Start the bot"""
    # Create application with increased timeout for file uploads
    from telegram.request import HTTPXRequest

    # Increase timeouts for large file uploads (audio files can be big)
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=120.0,  # 2 minutes for reading responses
        write_timeout=120.0,  # 2 minutes for uploading files
        connect_timeout=10.0,  # 10 seconds for initial connection
        pool_timeout=10.0
    )

    application = Application.builder().token(BOT_TOKEN).request(request).build()

    # Add core handlers (always enabled)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("ban", ban_user_command))
    application.add_handler(CommandHandler("unban", unban_user_command))
    application.add_handler(CommandHandler("updateytdlp", update_ytdlp))
    application.add_handler(CommandHandler("version", check_version))
    application.add_handler(CommandHandler("search", search_command))  # Admin-only text search
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))

    # OPTIONAL: Music Recognition Feature
    # This section is SAFE - if it fails, the bot continues working normally
    if ENABLE_MUSIC_RECOGNITION:
        try:
            from music_recognition import initialize_recognizer, is_enabled
            from music_handlers import MUSIC_HANDLERS

            # Initialize music recognizer
            if initialize_recognizer(ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET, ACRCLOUD_HOST):
                # Add music recognition handlers (audio and voice messages)
                application.add_handler(MessageHandler(filters.AUDIO, MUSIC_HANDLERS['audio']))
                application.add_handler(MessageHandler(filters.VOICE, MUSIC_HANDLERS['voice']))

                logger.info("✅ Music recognition feature ENABLED")
            else:
                logger.warning("⚠️ Music recognition initialization failed - feature DISABLED")

        except ImportError as e:
            logger.warning(f"⚠️ Music recognition module not available: {e}")
            logger.warning("⚠️ Music recognition feature DISABLED (bot works normally)")
        except Exception as e:
            logger.error(f"❌ Error loading music recognition: {e}")
            logger.error("❌ Music recognition feature DISABLED (bot works normally)")
    else:
        logger.info("ℹ️ Music recognition feature is DISABLED in config")

    # OPTIONAL: Text Search Feature (ADMIN ONLY - Testing)
    # This section is SAFE - if it fails, the bot continues working normally
    try:
        from text_search import initialize_searcher
        if initialize_searcher():
            logger.info("✅ Text search feature ENABLED (admin-only testing)")
        else:
            logger.warning("⚠️ Text search initialization failed - feature DISABLED")
    except ImportError as e:
        logger.warning(f"⚠️ Text search module not available: {e}")
        logger.warning("⚠️ Text search feature DISABLED (bot works normally)")
    except Exception as e:
        logger.error(f"❌ Error loading text search: {e}")
        logger.error("❌ Text search feature DISABLED (bot works normally)")

    # OPTIONAL: Large File Support (Up to 2GB)
    # This section is SAFE - if it fails, the bot works with 50MB limit
    try:
        from config import ENABLE_LARGE_FILES, API_ID, API_HASH
    except ImportError:
        ENABLE_LARGE_FILES = False
        API_ID = 0
        API_HASH = ""

    if ENABLE_LARGE_FILES and API_ID and API_HASH:
        try:
            from large_file_uploader import initialize_large_file_uploader
            import asyncio

            # Initialize large file uploader
            async def init_large_uploader():
                return await initialize_large_file_uploader(API_ID, API_HASH, BOT_TOKEN)

            loop = asyncio.get_event_loop()
            success = loop.run_until_complete(init_large_uploader())

            if success:
                logger.info("✅ Large file support ENABLED - 2GB uploads available!")
            else:
                logger.warning("⚠️ Large file initialization failed - using 50MB limit")

        except ImportError as e:
            logger.warning(f"⚠️ Large file module not available: {e}")
            logger.warning("⚠️ Large file support DISABLED (install pyrogram and tgcrypto)")
        except Exception as e:
            logger.error(f"❌ Error loading large file support: {e}")
            logger.error("❌ Large file support DISABLED (bot works with 50MB limit)")
    else:
        logger.info("ℹ️ Large file support is DISABLED (using 50MB limit)")
        if not API_ID or not API_HASH:
            logger.info("💡 To enable 2GB uploads, set API_ID and API_HASH in config.py")

    # Add error handler
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("🤖 Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
