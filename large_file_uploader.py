"""
Large File Uploader Module
Handles files up to 2GB using Telegram Client API (Pyrogram)

This module provides hybrid upload functionality:
- Files < 50MB: Uses Bot API (fast, simple)
- Files >= 50MB: Uses Client API (supports up to 2GB)
"""

import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import Pyrogram
try:
    from pyrogram import Client
    from pyrogram.types import Message
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False
    logger.warning("Pyrogram not installed. Large file support disabled.")


class LargeFileUploader:
    """Handle large file uploads using Pyrogram Client API"""

    def __init__(self, api_id: int, api_hash: str, bot_token: str):
        """
        Initialize large file uploader

        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API Hash from my.telegram.org
            bot_token: Bot token from BotFather
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.enabled = PYROGRAM_AVAILABLE and bool(api_id) and bool(api_hash)
        self.client: Optional[Client] = None

        if not PYROGRAM_AVAILABLE:
            logger.warning("Pyrogram not available. Install with: pip install pyrogram tgcrypto")
        elif not (api_id and api_hash):
            logger.warning("API_ID or API_HASH not configured. Large file support disabled.")

    async def initialize(self):
        """Initialize Pyrogram client"""
        if not self.enabled:
            return False

        try:
            # Create Pyrogram client
            self.client = Client(
                name="media_bot_client",
                api_id=self.api_id,
                api_hash=self.api_hash,
                bot_token=self.bot_token,
                workdir="."
            )

            # Start the client
            await self.client.start()
            logger.info("✅ Pyrogram client initialized - 2GB upload support ENABLED")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Pyrogram client: {e}")
            self.enabled = False
            return False

    async def stop(self):
        """Stop Pyrogram client"""
        if self.client:
            try:
                await self.client.stop()
                logger.info("Pyrogram client stopped")
            except Exception as e:
                logger.error(f"Error stopping Pyrogram client: {e}")

    async def upload_video(
        self,
        chat_id: int,
        file_path: str,
        caption: str = "",
        progress_callback=None
    ) -> bool:
        """
        Upload video file using Client API

        Args:
            chat_id: Telegram chat ID to send to
            file_path: Path to video file
            caption: Optional caption
            progress_callback: Optional progress callback function

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            logger.error("Large file uploader not enabled")
            return False

        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading video via Client API: {file_size / 1024 / 1024:.1f} MB")

            # Upload video
            await self.client.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=caption,
                supports_streaming=True,
                progress=progress_callback
            )

            logger.info("Video uploaded successfully via Client API")
            return True

        except Exception as e:
            logger.error(f"Error uploading video via Client API: {e}")
            return False

    async def upload_audio(
        self,
        chat_id: int,
        file_path: str,
        title: str = "",
        performer: str = "",
        caption: str = "",
        progress_callback=None
    ) -> bool:
        """
        Upload audio file using Client API

        Args:
            chat_id: Telegram chat ID to send to
            file_path: Path to audio file
            title: Song title
            performer: Artist name
            caption: Optional caption
            progress_callback: Optional progress callback function

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            logger.error("Large file uploader not enabled")
            return False

        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading audio via Client API: {file_size / 1024 / 1024:.1f} MB")

            # Upload audio
            await self.client.send_audio(
                chat_id=chat_id,
                audio=file_path,
                caption=caption,
                title=title,
                performer=performer,
                progress=progress_callback
            )

            logger.info("Audio uploaded successfully via Client API")
            return True

        except Exception as e:
            logger.error(f"Error uploading audio via Client API: {e}")
            return False

    async def upload_document(
        self,
        chat_id: int,
        file_path: str,
        caption: str = "",
        progress_callback=None
    ) -> bool:
        """
        Upload document file using Client API

        Args:
            chat_id: Telegram chat ID to send to
            file_path: Path to document file
            caption: Optional caption
            progress_callback: Optional progress callback function

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            logger.error("Large file uploader not enabled")
            return False

        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading document via Client API: {file_size / 1024 / 1024:.1f} MB")

            # Upload document
            await self.client.send_document(
                chat_id=chat_id,
                document=file_path,
                caption=caption,
                progress=progress_callback
            )

            logger.info("Document uploaded successfully via Client API")
            return True

        except Exception as e:
            logger.error(f"Error uploading document via Client API: {e}")
            return False


# Global instance
large_file_uploader: Optional[LargeFileUploader] = None


async def initialize_large_file_uploader(api_id: int, api_hash: str, bot_token: str) -> bool:
    """
    Initialize the global large file uploader

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash
        bot_token: Bot token

    Returns:
        True if initialized successfully, False otherwise
    """
    global large_file_uploader

    try:
        large_file_uploader = LargeFileUploader(api_id, api_hash, bot_token)

        if large_file_uploader.enabled:
            success = await large_file_uploader.initialize()
            if success:
                logger.info("✅ Large file uploader initialized - 2GB support ENABLED")
                return True
            else:
                logger.warning("⚠️ Large file uploader initialization failed")
                return False
        else:
            logger.info("ℹ️ Large file uploader DISABLED (missing Pyrogram or credentials)")
            return False

    except Exception as e:
        logger.error(f"❌ Error initializing large file uploader: {e}")
        return False


def is_large_file_enabled() -> bool:
    """Check if large file uploader is enabled and ready"""
    return large_file_uploader is not None and large_file_uploader.enabled


async def stop_large_file_uploader():
    """Stop the large file uploader"""
    if large_file_uploader:
        await large_file_uploader.stop()
