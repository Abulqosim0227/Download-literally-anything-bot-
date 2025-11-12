"""
Text-based Song Search Module (Admin Testing)
Search for songs by name, artist, or lyrics using iTunes API

SAFE: Completely isolated, admin-only for testing
"""

import logging
import urllib.parse
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not installed. Text search disabled.")


class SongSearcher:
    """Handle text-based song search using iTunes API"""

    def __init__(self):
        """Initialize song searcher - iTunes API requires no keys!"""
        self.enabled = REQUESTS_AVAILABLE
        self.itunes_api = "https://itunes.apple.com/search"

        if not self.enabled:
            logger.warning("Text search is DISABLED. Missing requests library.")

    def search_songs(self, query: str, limit: int = 5) -> tuple[bool, Optional[List[Dict]], Optional[str]]:
        """
        Search for songs by text query

        Args:
            query: Search text (song name, artist, lyrics)
            limit: Number of results (default 5)

        Returns:
            (success, results_list, error_message)
        """
        if not self.enabled:
            return False, None, "Text search is not enabled. Install 'requests' library."

        try:
            # Prepare search parameters
            params = {
                'term': query,
                'media': 'music',
                'entity': 'song',
                'limit': limit
            }

            # Make request to iTunes API
            response = requests.get(self.itunes_api, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])

            if not results:
                return False, None, f"No songs found for: '{query}'\n\nTry:\n• Different spelling\n• Artist name + song name\n• More specific search terms"

            # Format results
            formatted_results = []
            for item in results:
                formatted_results.append({
                    'title': item.get('trackName', 'Unknown'),
                    'artist': item.get('artistName', 'Unknown'),
                    'album': item.get('collectionName', 'Unknown'),
                    'release_date': item.get('releaseDate', 'Unknown')[:10] if item.get('releaseDate') else 'Unknown',
                    'preview_url': item.get('previewUrl', ''),
                    'artwork': item.get('artworkUrl100', ''),
                    'itunes_url': item.get('trackViewUrl', ''),
                    'duration_ms': item.get('trackTimeMillis', 0)
                })

            return True, formatted_results, None

        except requests.exceptions.Timeout:
            return False, None, "Search timed out. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"iTunes API error: {e}")
            return False, None, f"Search failed: {str(e)[:100]}"
        except Exception as e:
            logger.error(f"Search error: {e}")
            return False, None, f"Error: {str(e)[:100]}"

    def get_youtube_search_url(self, title: str, artist: str) -> str:
        """Generate YouTube search URL for a song"""
        query = f"{artist} {title} official"
        encoded = urllib.parse.quote(query)
        return f"https://www.youtube.com/results?search_query={encoded}"

    def format_results(self, results: List[Dict]) -> str:
        """Format search results into readable text"""
        if not results:
            return "No results found."

        text = "🔍 Search Results:\n\n"

        for i, song in enumerate(results, 1):
            title = song.get('title', 'Unknown')
            artist = song.get('artist', 'Unknown')
            album = song.get('album', 'Unknown')
            year = song.get('release_date', 'Unknown')

            # Format duration
            duration_ms = song.get('duration_ms', 0)
            if duration_ms:
                duration_sec = duration_ms // 1000
                minutes = duration_sec // 60
                seconds = duration_sec % 60
                duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = "Unknown"

            text += f"{i}. 🎵 {title}\n"
            text += f"   🎤 {artist}\n"
            text += f"   💿 {album}\n"
            text += f"   📅 {year} • ⏱ {duration_str}\n\n"

        return text.strip()


# Global instance
song_searcher: Optional[SongSearcher] = None


def initialize_searcher() -> bool:
    """Initialize the global song searcher"""
    global song_searcher

    try:
        song_searcher = SongSearcher()
        if song_searcher.enabled:
            logger.info("✅ Text search initialized successfully!")
            return True
        else:
            logger.warning("⚠️ Text search initialization failed - missing dependencies")
            return False
    except Exception as e:
        logger.error(f"❌ Error initializing text search: {e}")
        return False


def is_enabled() -> bool:
    """Check if text search is enabled and working"""
    return song_searcher is not None and song_searcher.enabled
