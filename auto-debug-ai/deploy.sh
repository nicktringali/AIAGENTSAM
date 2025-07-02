#!/bin/bash
set -e

echo "🚀 Auto-Debug-AI Deployment Script"
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root for security reasons${NC}"
   exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to generate secure password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

echo "📋 Checking prerequisites..."

# Check Docker
if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    echo "Visit: https://docs.docker.com/engine/install/"
    exit 1
fi

# Check Docker Compose
if ! command_exists docker-compose; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}No .env file found. Creating from .env.example...${NC}"
    
    if [ ! -f .env.example ]; then
        echo -e "${RED}.env.example not found!${NC}"
        exit 1
    fi
    
    cp .env.example .env
    
    # Generate secure passwords
    REDIS_PASS=$(generate_password)
    SECRET_KEY=$(generate_password)
    API_KEY=$(generate_password)
    GRAFANA_PASS=$(generate_password)
    
    # Update .env with generated passwords
    sed -i.bak "s/your_secure_redis_password_here/$REDIS_PASS/g" .env
    sed -i.bak "s/your_very_secure_secret_key_here/$SECRET_KEY/g" .env
    sed -i.bak "s/your_api_authentication_key_here/$API_KEY/g" .env
    sed -i.bak "s/your_secure_grafana_password_here/$GRAFANA_PASS/g" .env
    
    echo -e "${YELLOW}Generated secure passwords. Please add your API keys to .env:${NC}"
    echo "  - OPENAI_API_KEY"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - Update CORS_ORIGINS with your domain"
    echo ""
    echo -e "${RED}Please edit .env file now and run this script again.${NC}"
    exit 1
fi

# Check if API keys are set
source .env
if [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ] || [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Please set OPENAI_API_KEY in .env file${NC}"
    exit 1
fi

if [ "$ANTHROPIC_API_KEY" = "your_anthropic_api_key_here" ] || [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${RED}Please set ANTHROPIC_API_KEY in .env file${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites checked${NC}"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/chroma
mkdir -p data/redis
mkdir -p logs

# Set proper permissions
chmod 755 data/chroma data/redis logs

echo -e "${GREEN}✓ Directories created${NC}"

# Pull latest images
echo "🐳 Pulling Docker images..."
docker-compose -f docker/docker-compose.yml pull

# Start services
echo "🚀 Starting services..."
docker-compose -f docker/docker-compose.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🏥 Checking service health..."
SERVICES=("auto-debug-ai" "redis" "chromadb" "prometheus" "grafana")
ALL_HEALTHY=true

for service in "${SERVICES[@]}"; do
    if docker-compose -f docker/docker-compose.yml ps | grep -q "$service.*Up"; then
        echo -e "  ${GREEN}✓ $service is running${NC}"
    else
        echo -e "  ${RED}✗ $service is not running${NC}"
        ALL_HEALTHY=false
    fi
done

if [ "$ALL_HEALTHY" = false ]; then
    echo -e "${RED}Some services failed to start. Check logs with:${NC}"
    echo "  docker-compose -f docker/docker-compose.yml logs"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Deployment successful!${NC}"
echo ""
echo "📊 Access points:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Grafana: http://localhost:3000 (admin/[password in .env])"
echo "  - Prometheus: http://localhost:9091"
echo ""
echo "🔐 Security notes:"
echo "  - API Key: $API_KEY"
echo "  - Remember to set up SSL/TLS with a reverse proxy"
echo "  - Configure firewall rules for production"
echo ""
echo "📝 Useful commands:"
echo "  - View logs: docker-compose -f docker/docker-compose.yml logs -f"
echo "  - Stop services: docker-compose -f docker/docker-compose.yml down"
echo "  - Restart services: docker-compose -f docker/docker-compose.yml restart"
echo "  - Check status: docker-compose -f docker/docker-compose.yml ps"