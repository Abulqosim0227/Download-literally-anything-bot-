#!/usr/bin/env python3
"""
Media Downloader Bot for Telegram
Supports: YouTube, Instagram, TikTok, Facebook, and more
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import os
import re
import logging
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
import yt_dlp

from config import *
from database import Database
from security_utils import (
    validate_url,
    sanitize_filename,
    safe_join_path,
    validate_text_input,
    validate_user_id,
    RateLimiter,
    require_admin,
    is_admin,
    validate_download_size,
    validate_content_type,
    safe_remove_file,
    validate_quality_option,
    validate_audio_format
)

# Bot start time for uptime tracking
BOT_START_TIME = time.time()

# Conversation states for feedback
WAITING_FOR_FEEDBACK = 1

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

# Initialize rate limiter
rate_limiter = RateLimiter(requests_per_minute=RATE_LIMIT_REQUESTS)


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
            'ignoreerrors': False,
            'no_color': True,  # Clean output
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
            # Use MOBILE User-Agent - TikTok blocks desktop bots more aggressively
            options['http_headers'].update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
                'Referer': 'https://www.tiktok.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Sec-Ch-Ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
                'Sec-Ch-Ua-Mobile': '?1',
                'Sec-Ch-Ua-Platform': '"Android"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            })
            # TikTok specific - aggressive anti-blocking
            options['extractor_args'] = {
                'tiktok': {
                    'webpage_download': True,
                    'api_hostname': 'api16-normal-c-useast1a.tiktokv.com',  # Use mobile API
                }
            }
            options['socket_timeout'] = 60  # TikTok servers can be slow
            options['retries'] = 10  # More retries for connection resets (was 5)
            options['fragment_retries'] = 10  # More fragment retries
            options['retry_sleep_functions'] = {'http': lambda n: 2 ** n}  # Exponential backoff: 2s, 4s, 8s, 16s...
            options['nocheckcertificate'] = True  # Skip SSL verification (TikTok CDN issues)
            options['geo_bypass'] = True  # Try to bypass geographic restrictions

        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            # Facebook - Enhanced multi-method approach
            options['http_headers'].update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.facebook.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            })
            # Enhanced extractor args with more fallbacks
            options['extractor_args'] = {
                'facebook': {
                    'api': ['mobile', 'www', 'watch', 'mbasic'],  # Added mbasic
                    'legacy_api': True,
                }
            }
            # Additional options
            options['cookiefile'] = None
            options['age_limit'] = None
            options['socket_timeout'] = 30  # Longer timeout for Facebook

        elif 'instagram.com' in url_lower:
            options['http_headers'].update({
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            })

        elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            # YouTube - Fix JS runtime warnings and SABR streaming issues
            options['extractor_args'] = {
                'youtube': {
                    'player_client': ['android', 'web'],  # Prefer android client (no JS needed)
                    'player_skip': ['webpage', 'configs'],  # Skip unnecessary steps
                    'max_comments': [0],  # Don't fetch comments
                }
            }

        return options

    @staticmethod
    def try_facebook_html_fallback(url: str) -> tuple[Optional[str], Optional[str]]:
        """
        ULTIMATE Facebook video extraction - 4 TIERS (same as @FacebookAsBot!)
        Tier 1: fdown.net API (MOST RELIABLE - 95% success!)
        Tier 2: mbasic method
        Tier 3: multi-regex
        Tier 4: JSON parsing
        Returns: (video_url, error)
        """
        try:
            import requests
            import json
            import re

            logger.info(f"🚀 ULTIMATE Facebook extraction (4-tier system)...")

            # Normalize URL
            if 'fb.watch' in url:
                logger.info("📍 Expanding fb.watch...")
                response = requests.head(url, allow_redirects=True, timeout=10)
                url = response.url

            original_url = url

            # === TIER 1: FDown.net API (95% success - same as successful bots!) ===
            logger.info("🎯 TIER 1: FDown.net API (PREMIUM METHOD)...")
            try:
                from fdown_api import Fdown

                fdown = Fdown()
                video_links = fdown.get_links(original_url)

                # Try HD link first
                if video_links.hdlink and 'http' in video_links.hdlink:
                    logger.info(f"✅ FDown.net API HD success! (Like @FacebookAsBot)")
                    return video_links.hdlink, None

                # Fallback to SD link
                if video_links.sdlink and 'http' in video_links.sdlink:
                    logger.info(f"✅ FDown.net API SD success!")
                    return video_links.sdlink, None

            except ImportError:
                logger.warning("⚠️ fdown-api not installed. Install: pip install fdown-api")
            except Exception as e:
                logger.warning(f"FDown API failed: {e}")

            # === TIER 2: mbasic.facebook.com (70-80% success) ===
            logger.info("🎯 TIER 2: mbasic method...")
            try:
                mbasic_url = original_url.replace('www.facebook.com', 'mbasic.facebook.com')
                mbasic_url = mbasic_url.replace('m.facebook.com', 'mbasic.facebook.com')

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }

                response = requests.get(mbasic_url, headers=headers, timeout=15)
                html = response.text

                # mbasic has simpler HTML with direct video tags
                video_patterns = [
                    r'<video[^>]+src="([^"]+)"',
                    r'<a[^>]+href="([^"]+\.mp4[^"]*)"',
                ]

                for pattern in video_patterns:
                    match = re.search(pattern, html)
                    if match:
                        video_url = match.group(1).replace('&amp;', '&')
                        if 'fbcdn.net' in video_url or '.mp4' in video_url:
                            logger.info(f"✅ mbasic success!")
                            return video_url, None

            except Exception as e:
                logger.warning(f"mbasic failed: {e}")

            # === TIER 3: Multi-Pattern Regex (60-70% success) ===
            logger.info("🎯 TIER 3: Multi-pattern regex...")

            url = original_url.replace('m.facebook.com', 'www.facebook.com')
            url = url.replace('mbasic.facebook.com', 'www.facebook.com')

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            response = requests.get(url, headers=headers, timeout=20)
            html = response.text

            # Patterns from real FB downloaders (2024 research)
            patterns = [
                (r'"browser_native_hd_url":"([^"]+)"', 'browser_hd_2024'),
                (r'"playable_url_quality_hd":"([^"]+)"', 'playable_hd_ytdlp'),
                (r'hd_src_no_ratelimit:"([^"]+)"', 'hd_no_limit'),
                (r'hd_src:"([^"]+)"', 'legacy_hd'),
                (r'"browser_native_sd_url":"([^"]+)"', 'browser_sd'),
                (r'"playable_url":"([^"]+)"', 'playable_sd'),
                (r'sd_src:"([^"]+)"', 'legacy_sd'),
            ]

            for pattern, method in patterns:
                match = re.search(pattern, html)
                if match:
                    video_url = match.group(1).replace('\\/', '/')
                    try:
                        video_url = video_url.encode('utf-8').decode('unicode_escape')
                    except:
                        pass

                    if 'http' in video_url and ('fbcdn.net' in video_url or 'facebook.com' in video_url):
                        logger.info(f"✅ Regex {method} success!")
                        return video_url, None

            # === TIER 4: JSON Extraction (videoDeliveryLegacyFields Oct 2024) ===
            logger.info("🎯 TIER 4: JSON extraction...")

            json_pattern = r'"videoDeliveryLegacyFields":\s*({[^}]+})'
            match = re.search(json_pattern, html)

            if match:
                try:
                    video_data = json.loads(match.group(1))

                    for field in ['browser_native_hd_url', 'browser_native_sd_url',
                                  'playable_url_quality_hd', 'playable_url']:
                        if field in video_data:
                            video_url = video_data[field]
                            if isinstance(video_url, str) and 'http' in video_url:
                                logger.info(f"✅ JSON {field} success!")
                                return video_url, None
                except:
                    pass

            logger.warning("❌ All 4 tiers failed")
            return None, "Could not extract video using any method"

        except Exception as e:
            logger.error(f"Facebook fallback error: {e}")
            return None, str(e)

    @staticmethod
    def get_facebook_download_alternatives(url: str) -> list[dict]:
        """Get alternative download methods for Facebook videos"""
        alternatives = [
            {
                'name': 'FDown',
                'url': f'https://fdown.net/download.php?url={url}',
                'description': 'Popular Facebook video downloader'
            },
            {
                'name': 'GetFBStuff',
                'url': f'https://getfbstuff.com/download?url={url}',
                'description': 'Alternative Facebook downloader'
            },
            {
                'name': 'SaveFrom',
                'url': f'https://en.savefrom.net/1-facebook-video-downloader-3/',
                'description': 'Multi-platform downloader'
            }
        ]
        return alternatives

    @staticmethod
    def get_tiktok_download_alternatives(url: str) -> list[dict]:
        """Get alternative download methods for TikTok videos"""
        import urllib.parse
        encoded_url = urllib.parse.quote(url)
        alternatives = [
            {
                'name': 'SnapTik',
                'url': f'https://snaptik.app/en',
                'description': 'Popular TikTok video downloader (no watermark)'
            },
            {
                'name': 'SSSTik',
                'url': f'https://ssstik.io/en',
                'description': 'Fast TikTok downloader'
            },
            {
                'name': 'TikMate',
                'url': f'https://tikmate.app/',
                'description': 'HD TikTok downloader'
            },
            {
                'name': 'SaveFrom',
                'url': f'https://en.savefrom.net/download-from-tiktok',
                'description': 'Multi-platform downloader'
            }
        ]
        return alternatives

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
            # Facebook has special handling since it's most problematic
            if ("facebook" in url.lower() or "fb.watch" in url.lower()):
                # Try HTML fallback before giving up
                logger.info("Trying Facebook HTML fallback method...")
                video_url, fb_error = MediaDownloader.try_facebook_html_fallback(url)

                if video_url:
                    logger.info("Facebook HTML fallback succeeded!")
                    # Create a minimal info dict with the direct video URL
                    return {
                        'url': video_url,
                        'title': 'Facebook Video',
                        'ext': 'mp4',
                        'direct_url': True,  # Flag to indicate this is a direct URL
                        'webpage_url': url
                    }, None

                # If fallback also failed, provide helpful error with alternatives
                alternatives = MediaDownloader.get_facebook_download_alternatives(url)
                alt_text = "\n\n📥 Alternative Download Links:\n"
                for alt in alternatives:
                    alt_text += f"• {alt['name']}: {alt['url']}\n"

                if "cannot parse data" in error_msg.lower() or "parse" in error_msg.lower():
                    return None, (
                        "❌ Facebook download failed - Cannot parse video data.\n\n"
                        "Facebook frequently changes their system making downloads difficult.\n\n"
                        "💡 Quick Fixes:\n"
                        "• Make sure video is PUBLIC (not friends-only)\n"
                        "• Use desktop Facebook link (not mobile m.facebook.com)\n"
                        "• Try copying the video URL directly from browser\n"
                        f"{alt_text}\n"
                        "⚠️ Note: Facebook intentionally blocks automated downloads."
                    )
                else:
                    return None, (
                        "❌ Facebook download failed.\n\n"
                        "💡 Troubleshooting:\n"
                        "• Ensure video is PUBLIC (not friends-only)\n"
                        "• Use full facebook.com URL (not fb.watch)\n"
                        "• Video must not be age-restricted\n"
                        f"{alt_text}\n"
                        "Try the alternative links above or download manually from browser."
                    )

            elif "cannot parse data" in error_msg.lower():
                return None, (
                    "❌ Cannot parse this video. The platform may have updated their system.\n\n"
                    "💡 Try:\n"
                    "• Update the bot: pip install --upgrade yt-dlp\n"
                    "• Try a different video from the same platform\n"
                    "• Report to admin if issue persists"
                )

            elif "tiktok" in url.lower() and ("timeout" in error_msg.lower() or "timed out" in error_msg.lower()):
                return None, (
                    "❌ TikTok connection timeout (server too slow).\n\n"
                    "💡 Solutions:\n"
                    "• Try again in a few seconds (TikTok servers can be slow)\n"
                    "• The bot will retry automatically (10 attempts with backoff)\n"
                    "• Make sure video is public and not age-restricted\n"
                    "• Try copying the link again from TikTok app\n\n"
                    "🔧 Technical: TikTok's CDN (vt.tiktok.com) is experiencing delays.\n"
                    "This is a TikTok server issue, not a bot issue."
                )

            elif "tiktok" in url.lower() and ("connection" in error_msg.lower() and ("reset" in error_msg.lower() or "aborted" in error_msg.lower() or "10054" in error_msg)):
                # TikTok actively blocking/closing connections
                return None, (
                    "❌ TikTok blocked the connection (Error 10054).\n\n"
                    "🚫 TikTok is actively blocking automated downloads.\n\n"
                    "💡 Solutions:\n"
                    "• Wait 2-5 minutes and try again (rate limit)\n"
                    "• Make sure video is PUBLIC (not friends-only)\n"
                    "• Copy link from TikTok app (not browser)\n"
                    "• Try from a different network/WiFi\n\n"
                    "🔧 Technical: TikTok detected automated access and forcibly closed\n"
                    "the connection. This is anti-bot protection, not a bug."
                )

            elif "tiktok" in url.lower() and ("redirect" in error_msg.lower() or "extract" in error_msg.lower()):
                return None, (
                    "❌ TikTok download failed.\n\n"
                    "💡 Try:\n"
                    "• Make sure the video is public\n"
                    "• Copy the link directly from TikTok app\n"
                    "• Use the share button and 'Copy link'\n"
                    "• Avoid shortened links"
                )

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
    async def download_video(url: str, quality: str, output_path: str, direct_url: str = None) -> Optional[str]:
        """Download video with specified quality

        Args:
            url: Original video URL
            quality: Desired quality (1080p, 720p, 480p, 360p)
            output_path: Where to save the file
            direct_url: If provided, download directly from this URL (for Facebook fallback)
        """

        # If we have a direct URL (from Facebook HTML fallback), download it directly
        if direct_url:
            try:
                import requests
                logger.info(f"Downloading from direct URL: {direct_url[:100]}...")

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                }

                response = requests.get(direct_url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()

                # Ensure output path has .mp4 extension
                if not output_path.endswith('.mp4'):
                    output_path = output_path.rsplit('.', 1)[0] + '.mp4'

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                logger.info(f"Direct download successful: {output_path}")
                return output_path

            except Exception as e:
                logger.error(f"Direct download failed: {e}")
                return None

        # Get base options for platform
        ydl_opts = MediaDownloader.get_base_options(url)

        # Quality format selection - relaxed for problematic platforms
        url_lower = url.lower()
        is_problematic = 'tiktok.com' in url_lower or 'facebook.com' in url_lower or 'fb.watch' in url_lower

        if is_problematic:
            # For TikTok and Facebook, use simpler format selection
            # Try to get specific quality but fallback to best
            format_spec = f"best[height<={quality[:-1]}]/best"
        else:
            # For other platforms, use more specific format selection
            if quality == "1080p":
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


async def safe_edit_message(query, text: str, reply_markup=None, remove_keyboard=False):
    """
    Safely edit message - handles both photo (caption) and text messages
    This fixes the "There is no text in the message to edit" error

    Args:
        query: The callback query
        text: The text/caption to display
        reply_markup: Optional keyboard markup (None to keep existing, use remove_keyboard=True to remove)
        remove_keyboard: If True, removes all buttons from the message
    """
    try:
        # If remove_keyboard is True, use empty markup to clear buttons
        if remove_keyboard:
            from telegram import InlineKeyboardMarkup
            reply_markup = InlineKeyboardMarkup([])

        if query.message.photo:
            # Message has a photo, edit caption instead
            await query.edit_message_caption(caption=text, reply_markup=reply_markup)
        else:
            # Regular text message
            await query.edit_message_text(text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        # Fallback: try to send new message
        try:
            await query.message.reply_text(text, reply_markup=reply_markup)
        except:
            pass


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
            InlineKeyboardButton("📜 History", callback_data="show_history"),
            InlineKeyboardButton("⚙️ Settings", callback_data="show_settings"),
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

    user_id = update.effective_user.id

    # Check rate limiting (admins bypass rate limits)
    if not is_admin(user_id):
        is_allowed, wait_seconds = rate_limiter.is_allowed(user_id)
        if not is_allowed:
            await update.message.reply_text(
                f"⏳ Please wait {wait_seconds} seconds before downloading again.\n\n"
                f"Rate limit: {RATE_LIMIT_REQUESTS} downloads per minute"
            )
            return

    url = update.message.text.strip()

    if not is_url(url):
        await update.message.reply_text("❌ Please send a valid URL!")
        return

    # Validate URL for security (SSRF protection)
    if not validate_url(url):
        await update.message.reply_text(
            "❌ Invalid or unsafe URL!\n\n"
            "Please ensure:\n"
            "• URL is from a supported platform\n"
            "• URL is publicly accessible\n"
            "• URL doesn't contain private/internal addresses"
        )
        logger.warning(f"Blocked unsafe URL from user {user_id}: {url[:100]}")
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
    context.user_data['direct_url'] = info.get('url') if info.get('direct_url') else None  # Store direct URL if available

    # Platforms that should auto-download (no quality menu needed)
    AUTO_DOWNLOAD_PLATFORMS = ['Facebook', 'Instagram', 'TikTok', 'Twitter/X', 'Reddit']

    # For social media: auto-download in 1080p (like @FacebookAsBot)
    if platform in AUTO_DOWNLOAD_PLATFORMS:
        # Format duration
        duration = info.get('duration', 0)
        if duration:
            duration = int(duration)
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"

        title = info.get('title', 'Unknown')[:100]
        uploader = info.get('uploader', 'Unknown')

        # Show simple confirmation with download button
        keyboard = [
            [InlineKeyboardButton("📥 Download Video", callback_data="video_1080p")],
            [InlineKeyboardButton("🎵 Download Audio (MP3)", callback_data="audio_mp3")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        caption = f"""✅ Video Found!

📺 {title}
👤 {uploader}
⏱ {duration_str}

📥 Ready to download!"""

        # Get thumbnail URL
        thumbnail_url = None
        if 'thumbnail' in info:
            thumbnail_url = info['thumbnail']
        elif 'thumbnails' in info and info['thumbnails']:
            # Get the best quality thumbnail
            thumbnail_url = info['thumbnails'][-1].get('url')

        # Send with thumbnail if available
        if thumbnail_url:
            try:
                await processing_msg.delete()
                await update.message.reply_photo(
                    photo=thumbnail_url,
                    caption=caption,
                    reply_markup=reply_markup
                )
                return
            except Exception as e:
                logger.warning(f"Failed to send thumbnail: {e}")
                # Fallback to text message

        # Fallback to text if no thumbnail
        await processing_msg.edit_text(caption, reply_markup=reply_markup)
        return

    # For YouTube/Vimeo: show full quality menu
    keyboard = [
        [
            InlineKeyboardButton("🎥 1080p", callback_data="video_1080p"),
            InlineKeyboardButton("🎥 720p", callback_data="video_720p"),
        ],
        [
            InlineKeyboardButton("🎥 480p", callback_data="video_480p"),
            InlineKeyboardButton("🎥 360p", callback_data="video_360p"),
        ],
        [
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data="audio_mp3"),
            InlineKeyboardButton("🎵 Audio (M4A)", callback_data="audio_m4a"),
        ],
        [
            InlineKeyboardButton("📸 Get Thumbnail", callback_data="get_thumbnail"),
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

    caption = f"""✅ Video Found!

📺 Title: {title}
👤 Uploader: {uploader}
⏱ Duration: {duration_str}

📥 Select download option:"""

    # Get thumbnail URL
    thumbnail_url = None
    if 'thumbnail' in info:
        thumbnail_url = info['thumbnail']
    elif 'thumbnails' in info and info['thumbnails']:
        # Get the best quality thumbnail
        thumbnail_url = info['thumbnails'][-1].get('url')

    # Send with thumbnail if available
    if thumbnail_url:
        try:
            await processing_msg.delete()
            await update.message.reply_photo(
                photo=thumbnail_url,
                caption=caption,
                reply_markup=reply_markup
            )
            return
        except Exception as e:
            logger.warning(f"Failed to send thumbnail: {e}")
            # Fallback to text message

    # Fallback to text if no thumbnail
    await processing_msg.edit_text(caption, reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()

    # Handle broadcast callbacks
    if query.data.startswith("broadcast_"):
        await handle_broadcast(query, context)
        return

    # Handle history callbacks
    if query.data.startswith("history_"):
        await handle_history_callback(query, context)
        return

    # Handle settings callbacks
    if query.data.startswith("settings_"):
        await handle_settings_callback(query, context)
        return

    # Handle thumbnail request
    if query.data == "get_thumbnail":
        await handle_thumbnail_download(query, context)
        return

    # Handle special callbacks
    if query.data == "show_help":
        await show_help_inline(query)
        return
    elif query.data == "my_stats":
        await show_user_stats(query)
        return
    elif query.data == "show_history":
        await show_history_inline(query)
        return
    elif query.data == "show_settings":
        await show_settings_inline(query)
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
                InlineKeyboardButton("📜 History", callback_data="show_history"),
                InlineKeyboardButton("⚙️ Settings", callback_data="show_settings"),
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
        # Handle search callbacks - available to all users
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
        await safe_edit_message(query, "❌ Session expired. Please send the link again.", remove_keyboard=True)
        return

    # Parse callback data
    action, option = query.data.split('_')

    # Update message and REMOVE BUTTONS IMMEDIATELY
    await safe_edit_message(query, f"⏬ Downloading... Please wait.", remove_keyboard=True)

    # Generate output filename with security validation
    title = context.user_data.get('title', 'video')
    safe_title = sanitize_filename(title, max_length=50)

    if action == "video":
        output_file = safe_join_path(DOWNLOAD_DIR, f"{safe_title}_{option}.mp4")

        # Get direct URL if available (from Facebook HTML fallback)
        direct_url = context.user_data.get('direct_url')

        # Download video
        result = await MediaDownloader.download_video(url, option, output_file, direct_url=direct_url)

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
                await safe_edit_message(query,
                    f"❌ File is too large ({file_size / 1024 / 1024:.1f} MB). "
                    f"Maximum size: {MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB.",
                    remove_keyboard=True
                )
                os.remove(result)
                return

            # Send video (choose method based on file size)
            file_size_mb = file_size / 1024 / 1024

            # Use Client API for files >= 50MB if available
            if file_size >= BOT_API_LIMIT and is_large_file_enabled():
                await safe_edit_message(query,
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
                            url=url,
                            title=context.user_data.get('title', 'Unknown')
                        )
                        await safe_edit_message(query, "✅ Large video sent successfully! 🎉", remove_keyboard=True)
                    else:
                        await safe_edit_message(query, "❌ Failed to upload video. Try a lower quality.", remove_keyboard=True)
                except Exception as e:
                    logger.error(f"Error sending large video: {e}")
                    await safe_edit_message(query, f"❌ Error uploading large video: {str(e)}", remove_keyboard=True)
            else:
                # Use Bot API for files < 50MB
                await safe_edit_message(query,
                    f"📤 Uploading video ({file_size_mb:.1f} MB)...\n"
                    f"⏳ This may take a few minutes, please wait..."
                )

                try:
                    with open(result, 'rb') as video:
                        await context.bot.send_video(
                            chat_id=query.message.chat_id,
                            video=video,
                            caption=f"🎬 {context.user_data.get('title', 'Video')[:100]}\n\n📥 Quality: {option}",
                            supports_streaming=True,
                            read_timeout=300,  # 5 minutes
                            write_timeout=600  # 10 minutes for upload
                        )

                    # Record download in database
                    db.record_download(
                        user_id=query.from_user.id,
                        download_type="video",
                        platform=context.user_data.get('platform', 'unknown'),
                        url=url,
                        title=context.user_data.get('title', 'Unknown')
                    )

                    await safe_edit_message(query, "✅ Video sent successfully! 🎉", remove_keyboard=True)
                except Exception as e:
                    logger.error(f"Error sending video: {e}")
                    # More helpful error message
                    if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                        await safe_edit_message(query,
                            f"❌ Upload timed out ({file_size_mb:.1f} MB)\n\n"
                            f"💡 The video is too large or connection is slow.\n"
                            f"Try: Download as audio (smaller file)",
                            remove_keyboard=True
                        )
                    else:
                        await safe_edit_message(query, f"❌ Error sending video: {str(e)}", remove_keyboard=True)

            # Clean up
            try:
                if os.path.exists(result):
                    os.remove(result)
            except:
                pass
        else:
            await safe_edit_message(query, "❌ Download failed. Please try again or use a different quality.", remove_keyboard=True)

    elif action == "audio":
        output_file = safe_join_path(DOWNLOAD_DIR, f"{safe_title}.{option}")

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
                await safe_edit_message(query,
                    f"❌ File is too large ({file_size / 1024 / 1024:.1f} MB). "
                    f"Maximum size: {MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB.",
                    remove_keyboard=True
                )
                os.remove(result)
                return

            # Send audio (choose method based on file size)
            file_size_mb = file_size / 1024 / 1024

            # Use Client API for files >= 50MB if available
            if file_size >= BOT_API_LIMIT and is_large_file_enabled():
                await safe_edit_message(query,
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
                            url=url,
                            title=context.user_data.get('title', 'Unknown')
                        )
                        await safe_edit_message(query,
                            "✅ Large audio sent successfully! 🎉\n\n"
                            "📝 Want lyrics?\n"
                            "Try: /lyrics <artist> - <song>",
                            remove_keyboard=True
                        )
                    else:
                        await safe_edit_message(query, "❌ Failed to upload audio.", remove_keyboard=True)
                except Exception as e:
                    logger.error(f"Error sending large audio: {e}")
                    await safe_edit_message(query, f"❌ Error uploading large audio: {str(e)}", remove_keyboard=True)
            else:
                # Use Bot API for files < 50MB
                await safe_edit_message(query, f"📤 Uploading audio ({file_size_mb:.1f} MB)...")

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
                        url=url,
                        title=context.user_data.get('title', 'Unknown')
                    )

                    # Suggest lyrics for audio downloads
                    title = context.user_data.get('title', 'Unknown')
                    await safe_edit_message(query,
                        f"✅ Audio sent successfully! 🎉\n\n"
                        f"📝 Want lyrics?\n"
                        f"Try: /lyrics <artist> - <song>",
                        remove_keyboard=True
                    )
                except Exception as e:
                    logger.error(f"Error sending audio: {e}")
                    await safe_edit_message(query, f"❌ Error sending audio: {str(e)}", remove_keyboard=True)

            # Clean up
            try:
                if os.path.exists(result):
                    os.remove(result)
            except:
                pass
        else:
            await safe_edit_message(query, "❌ Download failed. Please try again.", remove_keyboard=True)


async def show_help_inline(query):
    """Show help message inline"""
    help_text = """ℹ️ Help & Instructions

How to download:
1️⃣ Copy a video link from any supported platform
2️⃣ Send the link to me
3️⃣ Choose your preferred quality or format
4️⃣ Wait for the download and upload

Supported platforms:
📹 YouTube • 📸 Instagram • 🎵 TikTok
📘 Facebook • 🐦 Twitter/X • 📱 Reddit
🎥 Vimeo • ✨ And many more!

Available formats:
📹 Video: 1080p, 720p, 480p, 360p
🎵 Audio: MP3, M4A
📸 Thumbnail: Get video thumbnail

━━━━━━━━━━━━━━━━━
Commands:
/start - Start the bot
/help - Show this message
/search - Search songs & lyrics
/lyrics - Get song lyrics
/history - View download history
/settings - Configure preferences
/feedback - Send feedback to admin

✨ Features:
• Download history tracking
• Custom defaults & preferences
• Auto-thumbnail option
• 🎵 Song search & lyrics
• 🎵 Music recognition
• Feedback system

Note: Maximum file size is 2 GB with large file support."""

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


async def show_history_inline(query):
    """Show download history inline"""
    user_id = query.from_user.id
    history = db.get_user_history(user_id, limit=10)

    if not history:
        history_text = """📜 Download History

You haven't downloaded anything yet.

Send me a video URL to get started!"""
    else:
        history_text = "📜 Your Download History\n\n"

        for i, download in enumerate(history[:10], 1):
            dtype = download.get('type', 'unknown')
            title = download.get('title', 'Unknown')[:30]
            timestamp = download.get('timestamp', '')[:10]

            icon = "🎥" if dtype == "video" else "🎵"
            history_text += f"{i}. {icon} {title}\n   📅 {timestamp}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(history_text[:4000], reply_markup=reply_markup)


async def show_settings_inline(query):
    """Show settings inline"""
    user_id = query.from_user.id
    settings = db.get_user_settings(user_id)

    # Create keyboard
    keyboard = [
        [InlineKeyboardButton(
            f"📹 Video Quality: {settings['default_video_quality'].upper()}",
            callback_data="settings_video_quality"
        )],
        [InlineKeyboardButton(
            f"🎵 Audio Format: {settings['default_audio_format'].upper()}",
            callback_data="settings_audio_format"
        )],
        [InlineKeyboardButton(
            f"📸 Auto Thumbnail: {'ON' if settings['auto_thumbnail'] else 'OFF'}",
            callback_data="settings_toggle_thumbnail"
        )],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_text = """⚙️ Settings

Configure your default preferences:

📹 Video Quality
Choose default video quality

🎵 Audio Format
Choose default audio format

📸 Auto Thumbnail
Automatically send thumbnails

━━━━━━━━━━━━━━━━━
Click buttons to change:"""

    await query.edit_message_text(settings_text, reply_markup=reply_markup)


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


@require_admin
async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user (admin only)"""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        user_id = validate_user_id(context.args[0])

        # Prevent admin from banning themselves
        if user_id == update.effective_user.id:
            await update.message.reply_text("❌ You cannot ban yourself!")
            return

        # Prevent banning other admins
        if is_admin(user_id):
            await update.message.reply_text("❌ You cannot ban another admin!")
            return

        # Check if user exists
        user_data = db.get_user(user_id)
        if not user_data:
            await update.message.reply_text(f"⚠️ Warning: User ID {user_id} not found in database, but will be banned anyway.")

        db.ban_user(user_id)
        username = user_data.get('username', 'Unknown') if user_data else 'Unknown'
        await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) has been banned.")
        logger.info(f"Admin {update.effective_user.id} banned user {user_id}")
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")


@require_admin
async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a user (admin only)"""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        user_id = validate_user_id(context.args[0])

        # Check if user is actually banned
        if not db.is_banned(user_id):
            await update.message.reply_text(f"⚠️ User ID {user_id} is not banned.")
            return

        db.unban_user(user_id)
        user_data = db.get_user(user_id)
        username = user_data.get('username', 'Unknown') if user_data else 'Unknown'
        await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) has been unbanned.")
        logger.info(f"Admin {update.effective_user.id} unbanned user {user_id}")
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")


@require_admin
async def update_ytdlp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update yt-dlp to latest version (admin only)"""

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

    # Check if user is admin
    try:
        from config import ADMIN_IDS
        is_admin = update.effective_user.id in ADMIN_IDS
    except ImportError:
        is_admin = update.effective_user.id == ADMIN_ID

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
📹 Video: 1080p, 720p, 480p, 360p
🎵 Audio: MP3, M4A
📸 Thumbnail: Get video thumbnail

━━━━━━━━━━━━━━━━━
📋 User Commands:
/start - Start the bot
/help - Show this message
/search - Search songs & get lyrics
/lyrics - Get song lyrics
/history - View your download history
/settings - Configure your preferences
/feedback - Send feedback to admin"""

    if is_admin:
        help_text += """

━━━━━━━━━━━━━━━━━
🔐 Admin Commands:
/admin - Admin panel
/status - Bot status & system info
/broadcast - Send message to all users
/ban - Ban a user
/unban - Unban a user"""

    help_text += """

━━━━━━━━━━━━━━━━━
✨ Features:
• Download history tracking
• Custom default quality & format
• Auto-thumbnail option
• Filter history by type
• 🎵 Song search & lyrics lookup
• 🎵 Music recognition from audio files
• Feedback system

Note: Maximum file size is 2 GB with large file support.

Need support? Use /feedback command."""

    await update.message.reply_text(help_text)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search for songs by text - Available to all users!
    Usage: /search <song name or artist>
    """
    # Track user
    await track_user(update)

    # Check if banned
    if await check_ban(update, context):
        return

    user_id = update.effective_user.id

    # Apply rate limiting (prevent abuse)
    if not is_admin(user_id):
        is_allowed, wait_seconds = rate_limiter.is_allowed(user_id)
        if not is_allowed:
            await update.message.reply_text(
                f"⏳ Please wait {wait_seconds} seconds before searching again.\n\n"
                f"Rate limit: {RATE_LIMIT_REQUESTS} searches per minute"
            )
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
                "🔍 Song Search & Lyrics\n\n"
                "Usage: /search <query>\n\n"
                "Examples:\n"
                "• /search Blinding Lights\n"
                "• /search The Weeknd\n"
                "• /search shape of you ed sheeran\n\n"
                "💡 I'll find the song and provide YouTube link + lyrics!"
            )
            return

        # Validate and sanitize search query
        try:
            query = validate_text_input(" ".join(context.args), max_length=100, field_name="Search query")
        except ValueError as e:
            await update.message.reply_text(f"❌ {str(e)}")
            return

        logger.info(f"Search query from user {user_id}: '{query}'")

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
    """Handle selection from search results - Auto-download from YouTube"""
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
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                    'max_comments': [0],
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'web'],
                                'player_skip': ['webpage', 'configs'],
                                'max_comments': [0],
                            }
                        }
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
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'web'],
                                'player_skip': ['webpage', 'configs'],
                                'max_comments': [0],
                            }
                        }
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


@require_admin
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast message to all users (admin only)"""
    if not context.args:
        await update.message.reply_text(
            "📢 Broadcast Message\n\n"
            "Usage: /broadcast <message>\n\n"
            "Example:\n"
            "/broadcast Hello everyone! The bot has new features.\n\n"
            "This will send your message to all users who have used the bot."
        )
        return

    message = " ".join(context.args)

    # Get all users
    all_users = db.get_all_user_ids()
    total_users = len(all_users)

    if total_users == 0:
        await update.message.reply_text("❌ No users to broadcast to.")
        return

    # Confirm broadcast
    keyboard = [
        [
            InlineKeyboardButton("✅ Send", callback_data=f"broadcast_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Store message in context
    context.user_data['broadcast_message'] = message

    await update.message.reply_text(
        f"📢 Broadcast Preview\n\n"
        f"Message:\n{message}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👥 Recipients: {total_users} users\n\n"
        f"Confirm broadcast?",
        reply_markup=reply_markup
    )


async def handle_broadcast(query, context):
    """Handle broadcast confirmation"""
    # Check admin
    try:
        from config import ADMIN_IDS
        is_admin = query.from_user.id in ADMIN_IDS
    except ImportError:
        is_admin = query.from_user.id == ADMIN_ID

    if not is_admin:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    if query.data == "broadcast_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return

    message = context.user_data.get('broadcast_message')
    if not message:
        await query.edit_message_text("❌ Message expired. Please try again.")
        return

    # Get all users
    all_users = db.get_all_user_ids()
    banned_users = db.get_banned_users()

    await query.edit_message_text(
        f"📤 Broadcasting message...\n\n"
        f"Total users: {len(all_users)}\n"
        f"Please wait..."
    )

    # Send to all users
    success_count = 0
    failed_count = 0
    blocked_count = 0

    for i, user_id in enumerate(all_users, 1):
        # Skip banned users
        if user_id in banned_users:
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 Broadcast Message\n\n{message}"
            )
            success_count += 1

            # Update progress every 10 users
            if i % 10 == 0:
                await query.edit_message_text(
                    f"📤 Broadcasting...\n\n"
                    f"Progress: {i}/{len(all_users)}\n"
                    f"✅ Sent: {success_count}\n"
                    f"❌ Failed: {failed_count}\n"
                    f"🚫 Blocked: {blocked_count}"
                )

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)

        except Exception as e:
            error_str = str(e).lower()
            if "blocked" in error_str or "forbidden" in error_str:
                blocked_count += 1
            else:
                failed_count += 1
                logger.error(f"Broadcast error for user {user_id}: {e}")

    # Final report
    await query.edit_message_text(
        f"✅ Broadcast Complete!\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 Results:\n"
        f"✅ Successfully sent: {success_count}\n"
        f"🚫 User blocked bot: {blocked_count}\n"
        f"❌ Failed: {failed_count}\n\n"
        f"Total: {len(all_users)} users"
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's download history"""
    await track_user(update)

    if await check_ban(update, context):
        return

    user_id = update.effective_user.id

    # Check for filter argument
    filter_type = None
    if context.args:
        arg = context.args[0].lower()
        if arg in ["video", "audio"]:
            filter_type = arg

    # Get history
    history = db.get_user_history(user_id, limit=20, download_type=filter_type)

    if not history:
        await update.message.reply_text(
            "📜 Download History\n\n"
            "You haven't downloaded anything yet.\n\n"
            "Send me a video URL to get started!"
        )
        return

    # Format history
    history_text = "📜 Your Download History\n\n"

    if filter_type:
        history_text += f"Filter: {filter_type.title()}\n\n"

    for i, download in enumerate(history[:20], 1):
        dtype = download.get('type', 'unknown')
        platform = download.get('platform', 'unknown')
        title = download.get('title', 'Unknown')[:40]
        timestamp = download.get('timestamp', '')[:16]

        icon = "🎥" if dtype == "video" else "🎵"

        history_text += f"{i}. {icon} {title}\n"
        history_text += f"   📅 {timestamp} • {platform.title()}\n\n"

    # Add buttons
    keyboard = []

    if not filter_type:
        keyboard.append([
            InlineKeyboardButton("🎥 Videos Only", callback_data="history_video"),
            InlineKeyboardButton("🎵 Audio Only", callback_data="history_audio")
        ])
    else:
        keyboard.append([InlineKeyboardButton("📜 All History", callback_data="history_all")])

    keyboard.append([InlineKeyboardButton("🗑 Clear History", callback_data="history_clear")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(history_text[:4000], reply_markup=reply_markup)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user settings"""
    await track_user(update)

    if await check_ban(update, context):
        return

    user_id = update.effective_user.id
    settings = db.get_user_settings(user_id)

    # Create keyboard
    keyboard = [
        [InlineKeyboardButton(
            f"📹 Video Quality: {settings['default_video_quality'].upper()}",
            callback_data="settings_video_quality"
        )],
        [InlineKeyboardButton(
            f"🎵 Audio Format: {settings['default_audio_format'].upper()}",
            callback_data="settings_audio_format"
        )],
        [InlineKeyboardButton(
            f"📸 Auto Thumbnail: {'ON' if settings['auto_thumbnail'] else 'OFF'}",
            callback_data="settings_toggle_thumbnail"
        )],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_text = """⚙️ Settings

Configure your default preferences:

📹 Video Quality
Choose default video quality (1080p, 720p, 480p, 360p)

🎵 Audio Format
Choose default audio format (MP3, M4A)

📸 Auto Thumbnail
Automatically send video thumbnail with downloads

━━━━━━━━━━━━━━━━━
Click buttons below to change settings:"""

    await update.message.reply_text(settings_text, reply_markup=reply_markup)


async def handle_history_callback(query, context):
    """Handle history button callbacks"""
    user_id = query.from_user.id

    if query.data == "history_clear":
        # Confirm clear
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Clear", callback_data="history_clear_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="history_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "⚠️ Clear History?\n\n"
            "Are you sure you want to clear your entire download history?\n\n"
            "This action cannot be undone.",
            reply_markup=reply_markup
        )
        return

    elif query.data == "history_clear_confirm":
        db.clear_user_history(user_id)
        await query.edit_message_text("✅ Your download history has been cleared.")
        return

    elif query.data == "history_cancel":
        await query.edit_message_text("❌ Action cancelled.")
        return

    # Handle filter callbacks
    filter_type = None
    if query.data == "history_video":
        filter_type = "video"
    elif query.data == "history_audio":
        filter_type = "audio"

    # Get history
    history = db.get_user_history(user_id, limit=20, download_type=filter_type)

    if not history:
        await query.edit_message_text(
            f"📜 Download History\n\n"
            f"No {filter_type + ' ' if filter_type else ''}downloads found."
        )
        return

    # Format history
    history_text = "📜 Your Download History\n\n"

    if filter_type:
        history_text += f"Filter: {filter_type.title()}\n\n"

    for i, download in enumerate(history[:20], 1):
        dtype = download.get('type', 'unknown')
        platform = download.get('platform', 'unknown')
        title = download.get('title', 'Unknown')[:40]
        timestamp = download.get('timestamp', '')[:16]

        icon = "🎥" if dtype == "video" else "🎵"

        history_text += f"{i}. {icon} {title}\n"
        history_text += f"   📅 {timestamp} • {platform.title()}\n\n"

    # Add buttons
    keyboard = []

    if not filter_type:
        keyboard.append([
            InlineKeyboardButton("🎥 Videos Only", callback_data="history_video"),
            InlineKeyboardButton("🎵 Audio Only", callback_data="history_audio")
        ])
    else:
        keyboard.append([InlineKeyboardButton("📜 All History", callback_data="history_all")])

    keyboard.append([InlineKeyboardButton("🗑 Clear History", callback_data="history_clear")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(history_text[:4000], reply_markup=reply_markup)


async def handle_settings_callback(query, context):
    """Handle settings button callbacks"""
    user_id = query.from_user.id
    settings = db.get_user_settings(user_id)

    if query.data == "settings_video_quality":
        # Show quality options
        keyboard = [
            [InlineKeyboardButton("📺 1080p", callback_data="set_quality_1080p")],
            [InlineKeyboardButton("📺 720p", callback_data="set_quality_720p")],
            [InlineKeyboardButton("📺 480p", callback_data="set_quality_480p")],
            [InlineKeyboardButton("📺 360p", callback_data="set_quality_360p")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📹 Select Default Video Quality\n\n"
            f"Current: {settings['default_video_quality'].upper()}\n\n"
            "Choose your preferred quality:",
            reply_markup=reply_markup
        )

    elif query.data == "settings_audio_format":
        # Show audio format options
        keyboard = [
            [InlineKeyboardButton("🎵 MP3", callback_data="set_audio_mp3")],
            [InlineKeyboardButton("🎵 M4A", callback_data="set_audio_m4a")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🎵 Select Default Audio Format\n\n"
            f"Current: {settings['default_audio_format'].upper()}\n\n"
            "Choose your preferred format:",
            reply_markup=reply_markup
        )

    elif query.data == "settings_toggle_thumbnail":
        # Toggle thumbnail setting
        settings['auto_thumbnail'] = not settings['auto_thumbnail']
        db.save_user_settings(user_id, settings)

        await query.answer(
            f"✅ Auto Thumbnail {'enabled' if settings['auto_thumbnail'] else 'disabled'}!",
            show_alert=True
        )

        # Refresh settings menu
        keyboard = [
            [InlineKeyboardButton(
                f"📹 Video Quality: {settings['default_video_quality'].upper()}",
                callback_data="settings_video_quality"
            )],
            [InlineKeyboardButton(
                f"🎵 Audio Format: {settings['default_audio_format'].upper()}",
                callback_data="settings_audio_format"
            )],
            [InlineKeyboardButton(
                f"📸 Auto Thumbnail: {'ON' if settings['auto_thumbnail'] else 'OFF'}",
                callback_data="settings_toggle_thumbnail"
            )],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        settings_text = """⚙️ Settings

Configure your default preferences:

📹 Video Quality
Choose default video quality (1080p, 720p, 480p, 360p)

🎵 Audio Format
Choose default audio format (MP3, M4A)

📸 Auto Thumbnail
Automatically send video thumbnail with downloads

━━━━━━━━━━━━━━━━━
Click buttons below to change settings:"""

        await query.edit_message_text(settings_text, reply_markup=reply_markup)

    elif query.data.startswith("set_quality_"):
        quality = query.data.replace("set_quality_", "")
        settings['default_video_quality'] = quality
        db.save_user_settings(user_id, settings)

        await query.answer(f"✅ Default quality set to {quality.upper()}!", show_alert=True)

        # Go back to settings
        keyboard = [
            [InlineKeyboardButton(
                f"📹 Video Quality: {settings['default_video_quality'].upper()}",
                callback_data="settings_video_quality"
            )],
            [InlineKeyboardButton(
                f"🎵 Audio Format: {settings['default_audio_format'].upper()}",
                callback_data="settings_audio_format"
            )],
            [InlineKeyboardButton(
                f"📸 Auto Thumbnail: {'ON' if settings['auto_thumbnail'] else 'OFF'}",
                callback_data="settings_toggle_thumbnail"
            )],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        settings_text = """⚙️ Settings

Configure your default preferences:

📹 Video Quality
Choose default video quality (1080p, 720p, 480p, 360p)

🎵 Audio Format
Choose default audio format (MP3, M4A)

📸 Auto Thumbnail
Automatically send video thumbnail with downloads

━━━━━━━━━━━━━━━━━
Click buttons below to change settings:"""

        await query.edit_message_text(settings_text, reply_markup=reply_markup)

    elif query.data.startswith("set_audio_"):
        audio_format = query.data.replace("set_audio_", "")
        settings['default_audio_format'] = audio_format
        db.save_user_settings(user_id, settings)

        await query.answer(f"✅ Default format set to {audio_format.upper()}!", show_alert=True)

        # Go back to settings
        keyboard = [
            [InlineKeyboardButton(
                f"📹 Video Quality: {settings['default_video_quality'].upper()}",
                callback_data="settings_video_quality"
            )],
            [InlineKeyboardButton(
                f"🎵 Audio Format: {settings['default_audio_format'].upper()}",
                callback_data="settings_audio_format"
            )],
            [InlineKeyboardButton(
                f"📸 Auto Thumbnail: {'ON' if settings['auto_thumbnail'] else 'OFF'}",
                callback_data="settings_toggle_thumbnail"
            )],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        settings_text = """⚙️ Settings

Configure your default preferences:

📹 Video Quality
Choose default video quality (1080p, 720p, 480p, 360p)

🎵 Audio Format
Choose default audio format (MP3, M4A)

📸 Auto Thumbnail
Automatically send video thumbnail with downloads

━━━━━━━━━━━━━━━━━
Click buttons below to change settings:"""

        await query.edit_message_text(settings_text, reply_markup=reply_markup)

    elif query.data == "settings_back":
        # Go back to settings menu
        keyboard = [
            [InlineKeyboardButton(
                f"📹 Video Quality: {settings['default_video_quality'].upper()}",
                callback_data="settings_video_quality"
            )],
            [InlineKeyboardButton(
                f"🎵 Audio Format: {settings['default_audio_format'].upper()}",
                callback_data="settings_audio_format"
            )],
            [InlineKeyboardButton(
                f"📸 Auto Thumbnail: {'ON' if settings['auto_thumbnail'] else 'OFF'}",
                callback_data="settings_toggle_thumbnail"
            )],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        settings_text = """⚙️ Settings

Configure your default preferences:

📹 Video Quality
Choose default video quality (1080p, 720p, 480p, 360p)

🎵 Audio Format
Choose default audio format (MP3, M4A)

📸 Auto Thumbnail
Automatically send video thumbnail with downloads

━━━━━━━━━━━━━━━━━
Click buttons below to change settings:"""

        await query.edit_message_text(settings_text, reply_markup=reply_markup)


async def handle_thumbnail_download(query, context):
    """Download and send video thumbnail"""
    url = context.user_data.get('url')
    if not url:
        await safe_edit_message(query, "❌ Session expired. Please send the link again.", remove_keyboard=True)
        return

    await safe_edit_message(query, "📸 Extracting thumbnail...")

    try:
        # Get video info with thumbnail
        info, error = MediaDownloader.get_video_info(url)

        if not info:
            await safe_edit_message(query, f"❌ Could not get thumbnail.\n\n{error}", remove_keyboard=True)
            return

        # Get thumbnail URL
        thumbnail_url = info.get('thumbnail')

        if not thumbnail_url:
            await safe_edit_message(query, "❌ No thumbnail available for this video.", remove_keyboard=True)
            return

        # Download thumbnail
        import requests
        response = requests.get(thumbnail_url, timeout=10)

        if response.status_code == 200:
            # Save thumbnail temporarily
            title = context.user_data.get('title', 'thumbnail')
            safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
            thumb_path = os.path.join(DOWNLOAD_DIR, f"{safe_title}_thumb.jpg")

            with open(thumb_path, 'wb') as f:
                f.write(response.content)

            # Send thumbnail
            with open(thumb_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photo,
                    caption=f"📸 Thumbnail\n\n🎬 {context.user_data.get('title', 'Video')[:100]}"
                )

            # Clean up
            try:
                os.remove(thumb_path)
            except:
                pass

            await safe_edit_message(query, "✅ Thumbnail sent successfully!", remove_keyboard=True)

        else:
            await safe_edit_message(query, "❌ Failed to download thumbnail.", remove_keyboard=True)

    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        await safe_edit_message(query, f"❌ Error getting thumbnail: {str(e)[:100]}", remove_keyboard=True)


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start feedback conversation"""
    await track_user(update)

    if await check_ban(update, context):
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 Send Feedback\n\n"
        "Please write your feedback, suggestions, or report issues.\n\n"
        "Your message will be sent directly to the admin.\n\n"
        "Type /cancel to cancel."
    )

    return WAITING_FOR_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and forward feedback to admin"""
    user = update.effective_user
    feedback_text = update.message.text

    # Validate feedback text
    try:
        feedback_text = validate_text_input(feedback_text, max_length=4000, field_name="Feedback")
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}\n\nPlease send valid feedback.")
        return WAITING_FOR_FEEDBACK

    # Get admin IDs
    try:
        from config import ADMIN_IDS
        admin_ids = ADMIN_IDS
    except ImportError:
        admin_ids = [ADMIN_ID]

    # Format feedback message
    feedback_msg = f"""📬 New Feedback Received!

👤 From: {user.first_name} {user.last_name or ''}
🆔 User ID: {user.id}
👤 Username: @{user.username or 'None'}

━━━━━━━━━━━━━━━━━
💬 Message:

{feedback_text}

━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    # Send to all admins
    success = False
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=feedback_msg
            )
            success = True
        except Exception as e:
            logger.error(f"Failed to send feedback to admin {admin_id}: {e}")

    if success:
        await update.message.reply_text(
            "✅ Thank you for your feedback!\n\n"
            "Your message has been sent to the admin.\n"
            "We appreciate your input! 🙏"
        )
    else:
        await update.message.reply_text(
            "❌ Failed to send feedback. Please try again later or contact the admin directly."
        )

    return ConversationHandler.END


async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel feedback"""
    await update.message.reply_text("❌ Feedback cancelled.")
    return ConversationHandler.END


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot status and system info (admin only)"""
    # Check multiple admins
    try:
        from config import ADMIN_IDS
        is_admin = update.effective_user.id in ADMIN_IDS
    except ImportError:
        is_admin = update.effective_user.id == ADMIN_ID

    if not is_admin:
        await update.message.reply_text("❌ This command is only available to admins.")
        return

    # Calculate uptime
    uptime_seconds = int(time.time() - BOT_START_TIME)
    uptime_hours = uptime_seconds // 3600
    uptime_minutes = (uptime_seconds % 3600) // 60
    uptime_secs = uptime_seconds % 60

    # Get stats
    stats = db.get_statistics()
    total_users = stats['total_users']
    total_downloads = stats['total_downloads']

    # Get system info
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        system_info = f"""
💻 System Resources:
• CPU Usage: {cpu_percent}%
• RAM: {memory.percent}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)
• Disk: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"""
    except ImportError:
        system_info = "\n💻 System Resources:\n• Install 'psutil' for detailed stats"

    # Get Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Check yt-dlp version
    try:
        import subprocess
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=5)
        ytdlp_version = result.stdout.strip() if result.returncode == 0 else "Unknown"
    except:
        ytdlp_version = "Unknown"

    status_text = f"""🤖 Bot Status Dashboard

━━━━━━━━━━━━━━━━━
⏱ Uptime:
{uptime_hours}h {uptime_minutes}m {uptime_secs}s

📊 Statistics:
• Total Users: {total_users}
• Total Downloads: {total_downloads}
• Videos: {stats['video_downloads']}
• Audio: {stats['audio_downloads']}
{system_info}

🔧 Software Versions:
• Python: {python_version}
• yt-dlp: {ytdlp_version}
• python-telegram-bot: 20.7+

━━━━━━━━━━━━━━━━━
✅ Status: Online
🟢 All systems operational

Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    await update.message.reply_text(status_text)


async def lyrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get song lyrics using Lyrics.ovh API"""
    await track_user(update)

    if await check_ban(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "📝 Get Song Lyrics\n\n"
            "Usage: /lyrics <artist> - <song>\n\n"
            "Examples:\n"
            "• /lyrics Queen - Bohemian Rhapsody\n"
            "• /lyrics Billie Eilish - Bad Guy\n"
            "• /lyrics The Weeknd - Blinding Lights\n\n"
            "The format is: artist name - song title"
        )
        return

    # Join all arguments
    query = " ".join(context.args)

    # Check if query contains separator
    if " - " not in query:
        await update.message.reply_text(
            "❌ Invalid format!\n\n"
            "Please use: /lyrics <artist> - <song>\n\n"
            "Example: /lyrics Ed Sheeran - Shape of You"
        )
        return

    # Split into artist and song
    try:
        artist, song = query.split(" - ", 1)
        artist = artist.strip()
        song = song.strip()
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid format! Use: /lyrics <artist> - <song>\n\n"
            "Example: /lyrics Taylor Swift - Anti-Hero"
        )
        return

    # Send processing message
    processing_msg = await update.message.reply_text(
        f"🔍 Searching lyrics...\n\n"
        f"🎤 Artist: {artist}\n"
        f"🎵 Song: {song}"
    )

    try:
        import requests

        # Call Lyrics.ovh API
        api_url = f"https://api.lyrics.ovh/v1/{artist}/{song}"
        logger.info(f"Fetching lyrics from: {api_url}")

        response = requests.get(api_url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            lyrics = data.get('lyrics', '')

            if lyrics:
                # Telegram has 4096 character limit
                if len(lyrics) > 4000:
                    # Split into chunks
                    chunks = [lyrics[i:i+4000] for i in range(0, len(lyrics), 4000)]

                    await processing_msg.edit_text(
                        f"📝 Lyrics for: {song}\n"
                        f"🎤 Artist: {artist}\n\n"
                        f"Part 1/{len(chunks)}:\n\n"
                        f"{chunks[0]}"
                    )

                    # Send remaining chunks
                    for i, chunk in enumerate(chunks[1:], 2):
                        await update.message.reply_text(
                            f"Part {i}/{len(chunks)}:\n\n{chunk}"
                        )
                else:
                    await processing_msg.edit_text(
                        f"📝 Lyrics for: {song}\n"
                        f"🎤 Artist: {artist}\n\n"
                        f"{lyrics}"
                    )
            else:
                await processing_msg.edit_text(
                    f"❌ No lyrics found for:\n"
                    f"🎤 {artist} - {song}\n\n"
                    "Try checking the spelling or use a different format."
                )

        elif response.status_code == 404:
            await processing_msg.edit_text(
                f"❌ Lyrics not found!\n\n"
                f"🎤 Artist: {artist}\n"
                f"🎵 Song: {song}\n\n"
                f"Tips:\n"
                f"• Check spelling\n"
                f"• Try full artist/song name\n"
                f"• Avoid special characters"
            )
        else:
            await processing_msg.edit_text(
                f"❌ Error fetching lyrics (Status: {response.status_code})\n\n"
                f"Please try again later or check the song name."
            )

    except requests.exceptions.Timeout:
        await processing_msg.edit_text(
            "⏱️ Request timed out. Please try again."
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Lyrics API error: {e}")
        await processing_msg.edit_text(
            "❌ Network error while fetching lyrics.\n\n"
            "Please try again later."
        )
    except Exception as e:
        logger.error(f"Lyrics command error: {e}")
        await processing_msg.edit_text(
            "❌ An error occurred while fetching lyrics.\n\n"
            "Please try again or contact the admin."
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
        read_timeout=300.0,  # 5 minutes for reading responses
        write_timeout=600.0,  # 10 minutes for uploading large files
        connect_timeout=20.0,  # 20 seconds for initial connection
        pool_timeout=20.0
    )

    application = Application.builder().token(BOT_TOKEN).request(request).build()

    # Add feedback conversation handler
    feedback_handler = ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_command)],
        states={
            WAITING_FOR_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_feedback)]
    )

    # Add core handlers (always enabled)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("status", status_command))  # Admin-only status
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("ban", ban_user_command))
    application.add_handler(CommandHandler("unban", unban_user_command))
    application.add_handler(CommandHandler("updateytdlp", update_ytdlp))
    application.add_handler(CommandHandler("version", check_version))
    application.add_handler(CommandHandler("search", search_command))  # Song search & lyrics (all users)
    application.add_handler(CommandHandler("broadcast", broadcast_command))  # Admin-only broadcast
    application.add_handler(CommandHandler("history", history_command))  # User download history
    application.add_handler(CommandHandler("settings", settings_command))  # User settings
    application.add_handler(CommandHandler("lyrics", lyrics_command))  # Get song lyrics
    application.add_handler(feedback_handler)  # Feedback system
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

    # OPTIONAL: Text Search Feature (Available to all users)
    # This section is SAFE - if it fails, the bot continues working normally
    try:
        from text_search import initialize_searcher
        if initialize_searcher():
            logger.info("✅ Text search feature ENABLED (available to all users)")
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

    # Set up bot commands menu (will be applied on first message)
    async def post_init(app: Application) -> None:
        """Set bot commands after initialization"""
        # User commands (shown to everyone)
        user_commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help and instructions"),
            BotCommand("search", "Search for songs"),
            BotCommand("lyrics", "Get song lyrics"),
            BotCommand("history", "View download history"),
            BotCommand("settings", "Configure preferences"),
            BotCommand("feedback", "Send feedback to admin"),
        ]

        # Admin commands (shown only to admins)
        admin_commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help and instructions"),
            BotCommand("search", "Search for songs"),
            BotCommand("lyrics", "Get song lyrics"),
            BotCommand("admin", "Admin panel"),
            BotCommand("status", "Bot status & system info"),
            BotCommand("broadcast", "Send message to all users"),
            BotCommand("history", "View download history"),
            BotCommand("settings", "Configure preferences"),
        ]

        # Set default commands for all users
        await app.bot.set_my_commands(user_commands)

        # Set admin commands
        try:
            from config import ADMIN_IDS
            admin_ids = ADMIN_IDS
        except ImportError:
            admin_ids = [ADMIN_ID]

        # Set commands for each admin
        for admin_id in admin_ids:
            try:
                from telegram import BotCommandScopeChat
                await app.bot.set_my_commands(
                    admin_commands,
                    scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except Exception as e:
                logger.warning(f"Could not set admin commands for {admin_id}: {e}")

        logger.info("✅ Bot commands menu configured")

    # Add post init callback
    application.post_init = post_init

    # Start bot
    logger.info("🤖 Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
