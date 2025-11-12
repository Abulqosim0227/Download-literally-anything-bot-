"""
Music Recognition Module (Optional Feature)
Shazam-like functionality using ACRCloud API

This module is completely separate and optional.
If it breaks, disable it in config.py: ENABLE_MUSIC_RECOGNITION = False
"""

import os
import logging
import hashlib
import base64
import hmac
import time
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import ACRCloud - if not installed, feature won't work
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not installed. Music recognition disabled.")


class MusicRecognizer:
    """Handle music recognition using ACRCloud API"""

    def __init__(self, access_key: str = None, access_secret: str = None, host: str = None):
        """
        Initialize music recognizer

        Get free API keys from: https://www.acrcloud.com/
        Free tier: 2000 recognitions/day
        """
        self.access_key = access_key
        self.access_secret = access_secret
        self.host = host or "identify-eu-west-1.acrcloud.com"
        self.enabled = bool(access_key and access_secret and REQUESTS_AVAILABLE)

        if not self.enabled:
            logger.warning("Music recognition is DISABLED. Missing API keys or requests library.")

    def recognize_file(self, audio_file_path: str) -> Tuple[bool, Optional[dict], Optional[str]]:
        """
        Recognize music from audio file

        Returns:
            (success, song_data, error_message)
        """
        if not self.enabled:
            return False, None, "Music recognition is not enabled. Please configure ACRCloud API keys."

        try:
            # Read audio file
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()

            # Call ACRCloud API
            result = self._call_api(audio_data)

            if result and result.get('status', {}).get('code') == 0:
                # Success - extract song data
                metadata = result.get('metadata', {})
                music_list = metadata.get('music', [])

                if music_list:
                    song = music_list[0]  # Best match
                    return True, song, None
                else:
                    return False, None, "Song not found in database. Try a clearer recording."
            else:
                error_msg = result.get('status', {}).get('msg', 'Unknown error')
                return False, None, f"Recognition failed: {error_msg}"

        except FileNotFoundError:
            return False, None, "Audio file not found."
        except Exception as e:
            logger.error(f"Music recognition error: {e}")
            return False, None, f"Error: {str(e)}"

    def _call_api(self, audio_data: bytes) -> Optional[dict]:
        """Call ACRCloud API with audio data"""
        if not REQUESTS_AVAILABLE:
            return None

        try:
            # Prepare request
            http_method = "POST"
            http_uri = "/v1/identify"
            data_type = "audio"
            signature_version = "1"
            timestamp = str(int(time.time()))

            # Create signature
            string_to_sign = f"{http_method}\n{http_uri}\n{self.access_key}\n{data_type}\n{signature_version}\n{timestamp}"
            sign = base64.b64encode(
                hmac.new(
                    self.access_secret.encode('ascii'),
                    string_to_sign.encode('ascii'),
                    digestmod=hashlib.sha1
                ).digest()
            ).decode('ascii')

            # Prepare form data
            files = {
                'sample': audio_data
            }

            data = {
                'access_key': self.access_key,
                'sample_bytes': len(audio_data),
                'timestamp': timestamp,
                'signature': sign,
                'data_type': data_type,
                'signature_version': signature_version
            }

            # Send request
            url = f"https://{self.host}{http_uri}"
            response = requests.post(url, files=files, data=data, timeout=10)

            return response.json()

        except Exception as e:
            logger.error(f"ACRCloud API error: {e}")
            return None

    def format_song_info(self, song_data: dict) -> str:
        """Format song data into readable text"""
        try:
            title = song_data.get('title', 'Unknown')
            artists = song_data.get('artists', [])
            artist_name = artists[0].get('name', 'Unknown') if artists else 'Unknown'
            album = song_data.get('album', {}).get('name', 'Unknown')
            release_date = song_data.get('release_date', 'Unknown')

            # Get external links
            external_metadata = song_data.get('external_metadata', {})
            youtube = external_metadata.get('youtube', {})
            spotify = external_metadata.get('spotify', {})

            info_text = f"""✅ Song Identified!

🎵 Title: {title}
🎤 Artist: {artist_name}
💿 Album: {album}
📅 Released: {release_date}

━━━━━━━━━━━━━━━━━"""

            # Add links if available
            links = []
            if youtube:
                vid_id = youtube.get('vid')
                if vid_id:
                    links.append(f"▶️ YouTube: https://www.youtube.com/watch?v={vid_id}")

            if spotify:
                track_id = spotify.get('track', {}).get('id')
                if track_id:
                    links.append(f"🎧 Spotify: https://open.spotify.com/track/{track_id}")

            if links:
                info_text += "\n\n🔗 Links:\n" + "\n".join(links)

            return info_text

        except Exception as e:
            logger.error(f"Error formatting song info: {e}")
            return "Song found but error formatting details."

    def get_youtube_url(self, song_data: dict) -> Optional[str]:
        """Extract YouTube URL from song data"""
        try:
            external_metadata = song_data.get('external_metadata', {})
            youtube = external_metadata.get('youtube', {})
            vid_id = youtube.get('vid')

            if vid_id:
                return f"https://www.youtube.com/watch?v={vid_id}"
            return None

        except Exception as e:
            logger.error(f"Error extracting YouTube URL: {e}")
            return None


# Global instance (will be initialized in bot.py if enabled)
music_recognizer: Optional[MusicRecognizer] = None


def initialize_recognizer(access_key: str, access_secret: str, host: str = None) -> bool:
    """Initialize the global music recognizer"""
    global music_recognizer

    try:
        logger.info(f"Initializing music recognizer with host: {host}")
        logger.info(f"Access key present: {bool(access_key)}")
        logger.info(f"Access secret present: {bool(access_secret)}")
        logger.info(f"Requests available: {REQUESTS_AVAILABLE}")

        music_recognizer = MusicRecognizer(access_key, access_secret, host)

        if music_recognizer.enabled:
            logger.info("✅ Music recognition initialized successfully!")
            logger.info(f"✅ Using host: {music_recognizer.host}")
            return True
        else:
            logger.warning("⚠️ Music recognition initialization failed - missing dependencies or API keys")
            logger.warning(f"⚠️ Enabled status: {music_recognizer.enabled}")
            return False
    except Exception as e:
        logger.error(f"❌ Error initializing music recognizer: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def is_enabled() -> bool:
    """Check if music recognition is enabled and working"""
    return music_recognizer is not None and music_recognizer.enabled
