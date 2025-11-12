#!/bin/bash

echo "Starting Media Downloader Bot..."
echo "================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Warning: FFmpeg is not installed. Audio extraction may not work."
    echo "Install with: sudo apt install ffmpeg"
    echo ""
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create downloads directory
mkdir -p downloads

# Run the bot
echo ""
echo "Bot is starting..."
echo "Press Ctrl+C to stop"
echo "================================"
python3 bot.py
