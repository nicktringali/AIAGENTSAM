#!/bin/bash
# Health check script for Auto-Debug-AI

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🏥 Auto-Debug-AI Health Check"
echo "============================="
echo ""

# Function to check service
check_service() {
    local service=$1
    local port=$2
    local endpoint=$3
    
    echo -n "Checking $service... "
    
    if curl -s -f "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

# Function to check docker container
check_container() {
    local container=$1
    
    echo -n "Checking container $container... "
    
    if docker ps | grep -q "$container"; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${RED}✗ Not running${NC}"
        return 1
    fi
}

# Check Docker containers
echo "📦 Docker Containers:"
check_container "auto-debug-api"
check_container "auto-debug-redis"
check_container "auto-debug-chromadb"
check_container "auto-debug-prometheus"
check_container "auto-debug-grafana"
echo ""

# Check services
echo "🌐 Services:"
check_service "API" 8000 "/health"
check_service "Prometheus" 9091 "/metrics"
check_service "Grafana" 3000 "/api/health"
echo ""

# Check disk space
echo "💾 Disk Space:"
df -h | grep -E "^/dev/" | awk '{print $6 ": " $5 " used (" $4 " free)"}'
echo ""

# Check memory
echo "🧠 Memory Usage:"
free -h | grep Mem | awk '{print "Total: " $2 ", Used: " $3 ", Free: " $4}'
echo ""

# Check API response time
echo "⚡ API Response Time:"
if command -v curl > /dev/null 2>&1; then
    response_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8000/health || echo "N/A")
    if [ "$response_time" != "N/A" ]; then
        echo "Health endpoint: ${response_time}s"
    else
        echo -e "${RED}API not responding${NC}"
    fi
fi
echo ""

# Check logs for errors
echo "📝 Recent Errors (last 10):"
if [ -d "logs" ]; then
    grep -i error logs/*.log 2>/dev/null | tail -10 || echo "No recent errors found"
else
    echo "Log directory not found"
fi
echo ""

# Summary
echo "📊 Summary:"
all_good=true

if ! docker ps | grep -q "auto-debug-api"; then
    echo -e "${RED}⚠️  API container not running${NC}"
    all_good=false
fi

if ! docker ps | grep -q "auto-debug-redis"; then
    echo -e "${RED}⚠️  Redis container not running${NC}"
    all_good=false
fi

if ! docker ps | grep -q "auto-debug-chromadb"; then
    echo -e "${RED}⚠️  ChromaDB container not running${NC}"
    all_good=false
fi

if [ "$all_good" = true ]; then
    echo -e "${GREEN}✅ All systems operational${NC}"
else
    echo -e "${RED}❌ Some services need attention${NC}"
    exit 1
fi