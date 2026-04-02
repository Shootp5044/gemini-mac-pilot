#!/bin/bash
# Gemini Mac Pilot — One-command setup

set -e

echo "🚀 Setting up Gemini Mac Pilot..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Install it with: brew install python"
    exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install deps
echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet

# Install Playwright browser
echo "📦 Installing Playwright Chromium..."
python3 -m playwright install chromium

# Check .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env — add your GOOGLE_API_KEY"
    exit 1
fi

# Check portaudio (needed for pyaudio)
if ! brew list portaudio &> /dev/null 2>&1; then
    echo "📦 Installing portaudio..."
    brew install portaudio
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Usage:"
echo "  python main.py          # Voice + UI mode"
echo "  python main.py cli      # CLI mode (text input)"
echo "  python main.py ui       # UI + CLI mode (no voice)"
