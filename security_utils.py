"""
Security utilities for Media Downloader Bot
Provides input validation, sanitization, and security functions
"""

import os
import re
import logging
from urllib.parse import urlparse
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# URL Validation (Prevent SSRF and malicious URLs)
# ============================================================

def validate_url(url: str) -> bool:
    """
    Validate URL is safe to download from
    Prevents SSRF attacks by blocking internal networks

    Args:
        url: URL to validate

    Returns:
        True if URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            logger.warning(f"Invalid URL scheme: {parsed.scheme}")
            return False

        # Get hostname
        hostname = parsed.hostname
        if not hostname:
            logger.warning("URL has no hostname")
            return False

        hostname_lower = hostname.lower()

        # Blacklist internal/private networks (SSRF prevention)
        blocked_patterns = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '10.',
            '172.16.',
            '172.17.',
            '172.18.',
            '172.19.',
            '172.20.',
            '172.21.',
            '172.22.',
            '172.23.',
            '172.24.',
            '172.25.',
            '172.26.',
            '172.27.',
            '172.28.',
            '172.29.',
            '172.30.',
            '172.31.',
            '192.168.',
            '169.254.',  # Link-local
            'metadata.google.internal',  # Cloud metadata endpoints
            'metadata.goog',
            'metadata',
            '::1',  # IPv6 localhost
            'fc00:',  # IPv6 private
            'fd00:',  # IPv6 private
        ]

        for blocked in blocked_patterns:
            if hostname_lower.startswith(blocked) or blocked in hostname_lower:
                logger.warning(f"Blocked internal/private URL: {hostname}")
                return False

        # Whitelist allowed domains (optional - can be disabled)
        allowed_domains = [
            'youtube.com', 'youtu.be', 'youtube-nocookie.com',
            'facebook.com', 'fb.com', 'fb.watch', 'fbcdn.net',
            'instagram.com', 'cdninstagram.com',
            'tiktok.com', 'tiktokcdn.com',
            'twitter.com', 'x.com', 't.co', 'twimg.com',
            'reddit.com', 'redd.it', 'redditstatic.com',
            'vimeo.com', 'vimeocdn.com',
            'dailymotion.com', 'dm-event.net',
            'soundcloud.com', 'sndcdn.com',
            'twitch.tv', 'ttvnw.net',
            'streamable.com',
            'imgur.com',
        ]

        # Check if hostname ends with any allowed domain
        is_allowed = any(
            hostname_lower == domain or hostname_lower.endswith('.' + domain)
            for domain in allowed_domains
        )

        if not is_allowed:
            logger.info(f"URL not in whitelist (allowed but logged): {hostname}")
            # Note: Still allow it, just log for monitoring
            # Change to "return False" if you want strict whitelisting

        return True

    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False


# ============================================================
# File Path Sanitization (Prevent Path Traversal)
# ============================================================

def sanitize_filename(filename: str, max_length: int = 50) -> str:
    """
    Sanitize filename to prevent path traversal attacks

    Args:
        filename: Original filename
        max_length: Maximum length for filename

    Returns:
        Safe filename
    """
    # Remove any path components (handles both / and \)
    filename = os.path.basename(filename)

    # Remove dangerous characters (keep only alphanumeric, spaces, hyphens, underscores)
    safe = re.sub(r'[^\w\s-]', '', filename)

    # Replace multiple spaces with single space
    safe = re.sub(r'\s+', ' ', safe)

    # Trim to max length
    safe = safe[:max_length]

    # Remove leading/trailing whitespace, dots, and hyphens
    safe = safe.strip(' .-')

    # Ensure it's not empty
    if not safe:
        safe = 'download'

    return safe


def validate_output_path(output_path: str, base_dir: str) -> bool:
    """
    Validate that output path is within base directory
    Prevents path traversal attacks

    Args:
        output_path: Path to validate
        base_dir: Base directory that should contain the file

    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Convert to absolute paths
        output_abs = os.path.abspath(output_path)
        base_abs = os.path.abspath(base_dir)

        # Check if output is within base directory
        return output_abs.startswith(base_abs + os.sep) or output_abs.startswith(base_abs)
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return False


def safe_join_path(base_dir: str, filename: str) -> str:
    """
    Safely join base directory and filename

    Args:
        base_dir: Base directory
        filename: Filename to append

    Returns:
        Safe path

    Raises:
        ValueError: If resulting path is outside base directory
    """
    # Sanitize filename first
    safe_name = sanitize_filename(filename)

    # Join paths
    output_path = os.path.join(base_dir, safe_name)

    # Validate it's within base directory
    if not validate_output_path(output_path, base_dir):
        raise ValueError(f"Invalid path: {filename} escapes base directory")

    return output_path


# ============================================================
# Text Input Validation
# ============================================================

def validate_text_input(text: str, max_length: int = 4000, field_name: str = "Input") -> str:
    """
    Sanitize and validate text input

    Args:
        text: Input text
        max_length: Maximum allowed length
        field_name: Name of field for error messages

    Returns:
        Sanitized text

    Raises:
        ValueError: If input is invalid
    """
    if not text:
        raise ValueError(f"{field_name} cannot be empty")

    if len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or less")

    # Remove null bytes (can cause issues)
    text = text.replace('\x00', '')

    # Limit consecutive newlines
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    # Remove excessive whitespace
    text = text.strip()

    return text


def validate_user_id(user_id: any) -> int:
    """
    Validate user ID is a positive integer

    Args:
        user_id: User ID to validate

    Returns:
        Validated user ID as integer

    Raises:
        ValueError: If user ID is invalid
    """
    try:
        uid = int(user_id)
        if uid <= 0:
            raise ValueError("User ID must be positive")
        return uid
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid user ID: {user_id}") from e


# ============================================================
# Rate Limiting
# ============================================================

class RateLimiter:
    """Simple rate limiter for user actions"""

    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.user_requests = {}  # user_id -> list of timestamps

    def is_allowed(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Check if user is allowed to make a request

        Args:
            user_id: User ID

        Returns:
            Tuple of (is_allowed, wait_seconds)
        """
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Get user's request history
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        # Remove old requests
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id]
            if ts > cutoff
        ]

        # Check if limit exceeded
        if len(self.user_requests[user_id]) >= self.requests_per_minute:
            # Calculate wait time
            oldest = min(self.user_requests[user_id])
            wait_seconds = int((oldest - cutoff).total_seconds())
            return False, max(wait_seconds, 1)

        # Add current request
        self.user_requests[user_id].append(now)
        return True, None

    def reset_user(self, user_id: int):
        """Reset rate limit for a user (e.g., admin override)"""
        if user_id in self.user_requests:
            del self.user_requests[user_id]


# ============================================================
# Admin Authentication
# ============================================================

def is_admin(user_id: int) -> bool:
    """
    Check if user is an admin

    Args:
        user_id: User ID to check

    Returns:
        True if user is admin, False otherwise
    """
    try:
        # Try to import ADMIN_IDS first (newer config)
        from config import ADMIN_IDS
        return user_id in ADMIN_IDS
    except ImportError:
        # Fallback to ADMIN_ID (older config)
        try:
            from config import ADMIN_ID
            return user_id == ADMIN_ID
        except ImportError:
            logger.error("No admin configuration found")
            return False


def require_admin(func):
    """
    Decorator to require admin authentication for a function

    Usage:
        @require_admin
        async def admin_only_function(update, context):
            ...
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id

        if not is_admin(user_id):
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            await update.message.reply_text(
                "❌ Unauthorized. This command is only available to administrators."
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ============================================================
# File Size Validation
# ============================================================

def validate_download_size(content_length: Optional[int], max_size: int) -> bool:
    """
    Validate file size before download

    Args:
        content_length: Content-Length header value
        max_size: Maximum allowed size in bytes

    Returns:
        True if size is acceptable, False otherwise
    """
    if content_length is None:
        # If no Content-Length, we'll check during download
        logger.warning("No Content-Length header, size check deferred")
        return True

    try:
        size = int(content_length)
        if size > max_size:
            logger.warning(f"File too large: {size} bytes (max: {max_size})")
            return False
        return True
    except (TypeError, ValueError):
        logger.error(f"Invalid Content-Length: {content_length}")
        return False


def validate_content_type(content_type: Optional[str], allowed_types: List[str]) -> bool:
    """
    Validate content type is in allowed list

    Args:
        content_type: Content-Type header value
        allowed_types: List of allowed MIME type prefixes

    Returns:
        True if content type is allowed, False otherwise
    """
    if not content_type:
        logger.warning("No Content-Type header")
        # Allow if no content type specified (some servers don't send it)
        return True

    content_type_lower = content_type.lower()

    is_allowed = any(
        allowed.lower() in content_type_lower
        for allowed in allowed_types
    )

    if not is_allowed:
        logger.warning(f"Invalid content type: {content_type}")

    return is_allowed


# ============================================================
# Safe Resource Cleanup
# ============================================================

def safe_remove_file(filepath: str) -> bool:
    """
    Safely remove a file with proper error handling

    Args:
        filepath: Path to file to remove

    Returns:
        True if file was removed, False otherwise
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Removed file: {filepath}")
            return True
        else:
            logger.debug(f"File does not exist: {filepath}")
            return False
    except Exception as e:
        logger.error(f"Failed to remove file {filepath}: {e}")
        return False


# ============================================================
# Command Validation
# ============================================================

def validate_quality_option(quality: str) -> bool:
    """
    Validate video quality option

    Args:
        quality: Quality string (e.g., "1080p", "720p")

    Returns:
        True if valid, False otherwise
    """
    valid_qualities = ['1080p', '720p', '480p', '360p']
    return quality in valid_qualities


def validate_audio_format(format: str) -> bool:
    """
    Validate audio format option

    Args:
        format: Audio format string (e.g., "mp3", "m4a")

    Returns:
        True if valid, False otherwise
    """
    valid_formats = ['mp3', 'm4a', 'opus']
    return format in valid_formats
