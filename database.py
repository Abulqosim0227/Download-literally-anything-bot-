"""
Database module for user tracking and statistics
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class Database:
    """Simple JSON-based database for user management and statistics"""

    def __init__(self, db_file: str = "bot_data.json"):
        self.db_file = db_file
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """Load database from file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading database: {e}")
                return self._create_empty_db()
        return self._create_empty_db()

    def _create_empty_db(self) -> dict:
        """Create empty database structure"""
        return {
            "users": {},
            "banned_users": [],
            "statistics": {
                "total_downloads": 0,
                "video_downloads": 0,
                "audio_downloads": 0,
                "total_users": 0,
                "platform_stats": {}
            },
            "download_history": [],
            "user_settings": {}
        }

    def _save_data(self):
        """Save database to file"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving database: {e}")

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user in database"""
        user_id_str = str(user_id)

        if user_id_str not in self.data["users"]:
            self.data["statistics"]["total_users"] += 1
            self.data["users"][user_id_str] = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "total_downloads": 0,
                "video_downloads": 0,
                "audio_downloads": 0
            }
        else:
            # Update user info
            self.data["users"][user_id_str]["username"] = username
            self.data["users"][user_id_str]["first_name"] = first_name
            self.data["users"][user_id_str]["last_name"] = last_name
            self.data["users"][user_id_str]["last_seen"] = datetime.now().isoformat()

        self._save_data()

    def get_user(self, user_id: int) -> Optional[dict]:
        """Get user information"""
        return self.data["users"].get(str(user_id))

    def get_all_users(self) -> List[dict]:
        """Get all users"""
        return list(self.data["users"].values())

    def ban_user(self, user_id: int):
        """Ban a user"""
        if user_id not in self.data["banned_users"]:
            self.data["banned_users"].append(user_id)
            self._save_data()

    def unban_user(self, user_id: int):
        """Unban a user"""
        if user_id in self.data["banned_users"]:
            self.data["banned_users"].remove(user_id)
            self._save_data()

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        return user_id in self.data["banned_users"]

    def get_banned_users(self) -> List[int]:
        """Get list of banned user IDs"""
        return self.data["banned_users"]

    def record_download(self, user_id: int, download_type: str, platform: str = "unknown", url: str = "", title: str = ""):
        """Record a download in statistics"""
        # Update global stats
        self.data["statistics"]["total_downloads"] += 1

        if download_type == "video":
            self.data["statistics"]["video_downloads"] += 1
        elif download_type == "audio":
            self.data["statistics"]["audio_downloads"] += 1

        # Update platform stats
        if platform not in self.data["statistics"]["platform_stats"]:
            self.data["statistics"]["platform_stats"][platform] = 0
        self.data["statistics"]["platform_stats"][platform] += 1

        # Update user stats
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["total_downloads"] += 1
            if download_type == "video":
                self.data["users"][user_id_str]["video_downloads"] += 1
            elif download_type == "audio":
                self.data["users"][user_id_str]["audio_downloads"] += 1

        # Add to download history (keep last 1000)
        self.data["download_history"].append({
            "user_id": user_id,
            "type": download_type,
            "platform": platform,
            "url": url,
            "title": title,
            "timestamp": datetime.now().isoformat()
        })

        if len(self.data["download_history"]) > 1000:
            self.data["download_history"] = self.data["download_history"][-1000:]

        self._save_data()

    def get_statistics(self) -> dict:
        """Get overall statistics"""
        return self.data["statistics"]

    def get_recent_downloads(self, limit: int = 10) -> List[dict]:
        """Get recent downloads"""
        return self.data["download_history"][-limit:][::-1]

    def get_top_users(self, limit: int = 10) -> List[dict]:
        """Get top users by download count"""
        users = list(self.data["users"].values())
        sorted_users = sorted(users, key=lambda x: x["total_downloads"], reverse=True)
        return sorted_users[:limit]

    def get_user_history(self, user_id: int, limit: int = 20, download_type: str = None) -> List[dict]:
        """Get download history for a specific user"""
        user_downloads = [d for d in self.data["download_history"] if d["user_id"] == user_id]

        # Filter by type if specified
        if download_type:
            user_downloads = [d for d in user_downloads if d["type"] == download_type]

        # Return most recent first
        return user_downloads[-limit:][::-1]

    def clear_user_history(self, user_id: int):
        """Clear download history for a specific user"""
        self.data["download_history"] = [d for d in self.data["download_history"] if d["user_id"] != user_id]
        self._save_data()

    def get_user_settings(self, user_id: int) -> dict:
        """Get user settings"""
        user_id_str = str(user_id)
        if "user_settings" not in self.data:
            self.data["user_settings"] = {}

        if user_id_str not in self.data["user_settings"]:
            # Return default settings
            return {
                "default_video_quality": "1080p",
                "default_audio_format": "mp3",
                "auto_thumbnail": False
            }
        return self.data["user_settings"][user_id_str]

    def save_user_settings(self, user_id: int, settings: dict):
        """Save user settings"""
        user_id_str = str(user_id)
        if "user_settings" not in self.data:
            self.data["user_settings"] = {}

        self.data["user_settings"][user_id_str] = settings
        self._save_data()

    def get_all_user_ids(self) -> List[int]:
        """Get all user IDs for broadcasting"""
        return [int(uid) for uid in self.data["users"].keys()]
