#!/bin/bash
# Run script for Auto-Debug-AI

set -e

echo "🚀 Starting Auto-Debug-AI..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Run './setup.sh' first."
    exit 1
fi

# Check if API keys are set
if grep -q "your-openai-api-key-here" .env || grep -q "your-anthropic-api-key-here" .env; then
    echo "❌ Please set your API keys in .env file"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose -f docker/docker-compose.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check Redis
if docker exec auto-debug-redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not responding"
fi

# Check ChromaDB
if curl -s http://localhost:8001/api/v1/collections > /dev/null 2>&1; then
    echo "✅ ChromaDB is ready"
else
    echo "❌ ChromaDB is not responding"
fi

# Check API server
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API server is ready"
else
    echo "❌ API server is not responding"
fi

echo ""
echo "✨ Auto-Debug-AI is running!"
echo ""
echo "Services:"
echo "- API Server: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo "- Grafana: http://localhost:3000 (admin/admin)"
echo "- Prometheus: http://localhost:9091"
echo ""
echo "Usage:"
echo "- CLI: ./cli.py solve --bug-report 'your bug description'"
echo "- API: curl -X POST http://localhost:8000/solve -H 'Content-Type: application/json' -d '{\"bug_report\": \"your bug\"}''"
echo ""
echo "To stop: docker-compose -f docker/docker-compose.yml down"
echo ""