#!/bin/bash

echo "🔄 Updating yt-dlp..."
echo "━━━━━━━━━━━━━━━━━"

# Update yt-dlp
pip install --upgrade yt-dlp

# Check version
echo ""
echo "📦 New version:"
yt-dlp --version

echo ""
echo "✅ Update complete!"
echo ""
echo "💡 Restart your bot to apply changes:"
echo "   1. Stop bot (Ctrl+C)"
echo "   2. Start bot (python bot.py)"
