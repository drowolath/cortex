#!/bin/bash

# Start individual MCP servers for development/testing

echo "🔧 Starting individual MCP servers..."

# GitHub MCP Server 1
echo "Starting GitHub MCP Server 1 on port 8081..."
docker run -d \
  --name github-mcp-1 \
  --network cortex-network \
  -p 8081:8080 \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  cortex/mcp-server \
  python -m cortex.mcp.server_runner --server-type github --host 0.0.0.0 --port 8080

# GitHub MCP Server 2  
echo "Starting GitHub MCP Server 2 on port 8082..."
docker run -d \
  --name github-mcp-2 \
  --network cortex-network \
  -p 8082:8080 \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  cortex/mcp-server \
  python -m cortex.mcp.server_runner --server-type github --host 0.0.0.0 --port 8080

# Test direct launch (without Docker)
echo ""
echo "🚀 For direct testing without Docker:"
echo ""
echo "# GitHub MCP Server:"
echo "python -m cortex.mcp.server_runner --server-type github --host 0.0.0.0 --port 8081"
echo ""
echo "# With custom config:"
echo "python -m cortex.mcp.server_runner --server-type github --port 8081 --config '{\"github_token\": \"ghp_xxx\"}'"
echo ""
echo "# Test health:"
echo "curl http://localhost:8081/health"