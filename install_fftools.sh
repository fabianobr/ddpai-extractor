#!/usr/bin/env bash
# Install FFmpeg tools (ffmpeg, ffprobe) for video debugging

echo "🎬 FFmpeg Tools Installation"
echo "===================================="
echo ""

# Check if ffmpeg is installed
if command -v ffmpeg &> /dev/null; then
    echo "✅ ffmpeg is already installed"
    ffmpeg -version | head -1
else
    echo "❌ ffmpeg is NOT installed"
fi

echo ""

# Check if ffprobe is installed
if command -v ffprobe &> /dev/null; then
    echo "✅ ffprobe is already installed"
    ffprobe -version | head -1
else
    echo "❌ ffprobe is NOT installed (needed for video debugging)"
fi

echo ""
echo "===================================="
echo ""

# Determine OS and installation method
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "📦 macOS detected - Using Homebrew"
    echo ""

    # Check if brew is installed
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Install it first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi

    echo "Installing ffmpeg (includes ffprobe)..."
    brew install ffmpeg

    echo ""
    if command -v ffprobe &> /dev/null; then
        echo "✅ ffprobe installed successfully!"
        ffprobe -version | head -1
    else
        echo "❌ Installation failed - please try again manually"
        exit 1
    fi

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "📦 Linux detected - Using apt-get"
    echo ""
    echo "Installing ffmpeg (includes ffprobe)..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg

    echo ""
    if command -v ffprobe &> /dev/null; then
        echo "✅ ffprobe installed successfully!"
        ffprobe -version | head -1
    else
        echo "❌ Installation failed - please try again manually"
        exit 1
    fi

else
    echo "❌ Unknown OS: $OSTYPE"
    echo ""
    echo "Please install FFmpeg manually:"
    echo "  macOS: brew install ffmpeg"
    echo "  Linux: sudo apt-get install ffmpeg"
    echo "  Windows: Download from https://ffmpeg.org/download.html"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "You can now run the build script to see detailed video info:"
echo "  ./build.sh"
