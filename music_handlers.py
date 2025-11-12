"""
Music Recognition Handlers (Optional)
Telegram bot handlers for music recognition feature

SAFE: This file is only loaded if ENABLE_MUSIC_RECOGNITION = True
If disabled, these handlers are never registered and don't affect the bot
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pathlib import Path

import music_recognition  # Import module, not variable
from config import DOWNLOAD_DIR

logger = logging.getLogger(__name__)


async def handle_audio_for_recognition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle audio/voice messages for music recognition

    SAFE: Only called if music recognition is enabled
    """
    # Safety check - verify music_recognizer is initialized
    if music_recognition.music_recognizer is None or not music_recognition.is_enabled():
        await update.message.reply_text(
            "❌ Music recognition is not properly initialized.\n\n"
            "The download bot still works normally! Just send video URLs."
        )
        return

    # Get the audio file
    if update.message.voice:
        file = update.message.voice
        file_type = "voice message"
    elif update.message.audio:
        file = update.message.audio
        file_type = "audio file"
    else:
        return

    # Send "processing" message
    processing_msg = await update.message.reply_text(
        f"🎵 Analyzing your {file_type}...\n"
        f"🎤 Listening for music..."
    )

    try:
        # Download the audio file
        audio_file = await file.get_file()
        audio_path = os.path.join(DOWNLOAD_DIR, f"music_temp_{update.effective_user.id}.ogg")

        await audio_file.download_to_drive(audio_path)

        # Recognize the music
        success, song_data, error = music_recognition.music_recognizer.recognize_file(audio_path)

        # Clean up temp file
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if success and song_data:
            # Format the result
            song_info = music_recognition.music_recognizer.format_song_info(song_data)

            # Get YouTube URL if available
            youtube_url = music_recognition.music_recognizer.get_youtube_url(song_data)

            # Create keyboard with actions
            keyboard = []

            if youtube_url:
                keyboard.append([
                    InlineKeyboardButton("🎬 Download Video", callback_data=f"music_dl_video_{youtube_url}"),
                    InlineKeyboardButton("🎵 Download Audio", callback_data=f"music_dl_audio_{youtube_url}")
                ])
                keyboard.append([
                    InlineKeyboardButton("🔗 Open in YouTube", url=youtube_url)
                ])

            keyboard.append([InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")])

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            await processing_msg.edit_text(song_info, reply_markup=reply_markup)

        else:
            # Recognition failed
            error_msg = error or "Could not identify the song. Please try:\n• A clearer recording\n• Longer audio clip (at least 5 seconds)\n• Reduce background noise"
            await processing_msg.edit_text(f"❌ {error_msg}")

    except Exception as e:
        logger.error(f"Error in music recognition: {e}")
        await processing_msg.edit_text(
            f"❌ An error occurred during recognition.\n\n"
            f"This feature is experimental. The download bot still works normally!\n"
            f"Error: {str(e)[:100]}"
        )


async def handle_music_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle download callbacks from music recognition results

    SAFE: Reuses existing download functionality
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data.startswith("music_dl_"):
        # Extract URL from callback data
        parts = callback_data.split("_", 3)  # music_dl_video_URL or music_dl_audio_URL
        if len(parts) < 4:
            await query.edit_message_text("❌ Invalid callback data")
            return

        download_type = parts[2]  # video or audio
        url = parts[3]

        # Store URL in context like normal downloads
        context.user_data['url'] = url
        context.user_data['platform'] = 'YouTube'
        context.user_data['from_music_recognition'] = True

        # Show quality selection like normal downloads
        if download_type == "video":
            keyboard = [
                [
                    InlineKeyboardButton("🎥 Best Quality", callback_data="video_best"),
                    InlineKeyboardButton("🎥 720p", callback_data="video_720p"),
                ],
                [
                    InlineKeyboardButton("🎥 480p", callback_data="video_480p"),
                    InlineKeyboardButton("🎥 360p", callback_data="video_360p"),
                ]
            ]
        else:  # audio
            keyboard = [
                [
                    InlineKeyboardButton("🎵 MP3", callback_data="audio_mp3"),
                    InlineKeyboardButton("🎵 M4A", callback_data="audio_m4a"),
                ]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📥 Select quality:\n\n"
            "This uses the regular download system - safe and tested!",
            reply_markup=reply_markup
        )


# Export handlers for registration
MUSIC_HANDLERS = {
    'audio': handle_audio_for_recognition,
    'voice': handle_audio_for_recognition,
    'callback': handle_music_download_callback
}
