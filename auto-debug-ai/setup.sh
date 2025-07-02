#!/bin/bash
# Setup script for Auto-Debug-AI

set -e

echo "🚀 Setting up Auto-Debug-AI..."

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ is required. Found: $python_version"
    exit 1
fi
echo "✅ Python $python_version"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is required but not installed."
    exit 1
fi
echo "✅ Docker $(docker --version)"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is required but not installed."
    exit 1
fi
echo "✅ Docker Compose $(docker-compose --version)"

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p workspace logs chroma_db

# Copy environment file if not exists
if [ ! -f .env ]; then
    echo "🔧 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys!"
else
    echo "✅ .env file already exists"
fi

# Build Docker images
echo "🐳 Building Docker images..."
docker-compose -f docker/docker-compose.yml build

# Make CLI executable
chmod +x cli.py

echo ""
echo "✨ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your OpenAI and Anthropic API keys"
echo "2. Run './run.sh' to start the system"
echo "3. Use './cli.py --help' for CLI usage"
echo ""