#!/bin/bash

# Scale MCP servers horizontally

SERVER_TYPE=${1:-github}
SCALE_COUNT=${2:-3}

echo "📈 Scaling $SERVER_TYPE MCP servers to $SCALE_COUNT instances"

# Scale using docker-compose
docker-compose -f docker-compose.yml up -d --scale ${SERVER_TYPE}-mcp-1=$SCALE_COUNT

echo "✅ Scaled $SERVER_TYPE servers to $SCALE_COUNT instances"

# Show running containers
echo ""
echo "Running MCP containers:"
docker ps --filter "name=mcp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"