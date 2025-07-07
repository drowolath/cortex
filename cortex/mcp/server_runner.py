#!/usr/bin/env python3
"""
Independent MCP Server Runner
Runs MCP servers as standalone HTTP services that can be scaled horizontally
"""
import asyncio
import os
import sys
import argparse
import json
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import importlib

from ..core.logger import get_logger
from ..core.github_utils import GitHubUtils

logger = get_logger(__name__)


class MCPServerRunner:
    """Runs an MCP server as an independent HTTP service"""

    def __init__(self, server_type: str, config: Dict[str, Any]):
        self.server_type = server_type
        self.config = config
        self.app = FastAPI(
            title=f"MCP {server_type.title()} Server",
            description=f"Independent {server_type} MCP server",
            version="1.0.0",
        )
        self.mcp_module = None
        self.setup_middleware()
        self.setup_routes()

    def setup_middleware(self):
        """Setup FastAPI middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_routes(self):
        """Setup HTTP routes for MCP operations"""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "server_type": self.server_type,
                "version": "1.0.0",
            }

        @self.app.get("/info")
        async def server_info():
            """Get server information and available tools"""
            if not self.mcp_module:
                await self.load_mcp_module()

            tools = []
            if hasattr(self.mcp_module, "app") and hasattr(
                self.mcp_module.app, "_tools"
            ):
                tools = list(self.mcp_module.app._tools.keys())

            resources = []
            if hasattr(self.mcp_module, "app") and hasattr(
                self.mcp_module.app, "_resources"
            ):
                resources = list(self.mcp_module.app._resources.keys())

            return {
                "server_type": self.server_type,
                "tools": tools,
                "resources": resources,
                "config": self.config,
            }

        @self.app.post("/execute/{tool_name}")
        async def execute_tool(tool_name: str, parameters: Dict[str, Any]):
            """Execute a tool with parameters"""
            if not self.mcp_module:
                await self.load_mcp_module()

            try:
                # Apply credentials if provided
                await self.apply_credentials()

                # Get the tool function
                if hasattr(self.mcp_module, "app") and hasattr(
                    self.mcp_module.app, "_tools"
                ):
                    tool_func = self.mcp_module.app._tools.get(tool_name)
                    if not tool_func:
                        raise HTTPException(
                            status_code=404, detail=f"Tool '{tool_name}' not found"
                        )

                    # Execute the tool
                    result = await tool_func(**parameters)
                    return {"result": result}
                else:
                    raise HTTPException(
                        status_code=500, detail="MCP module not properly loaded"
                    )

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/resource/{resource_pattern:path}")
        async def get_resource(resource_pattern: str, **query_params):
            """Get a resource by pattern"""
            if not self.mcp_module:
                await self.load_mcp_module()

            try:
                # Apply credentials if provided
                await self.apply_credentials()

                # Get the resource function
                if hasattr(self.mcp_module, "app") and hasattr(
                    self.mcp_module.app, "_resources"
                ):
                    resource_func = self.mcp_module.app._resources.get(resource_pattern)
                    if not resource_func:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Resource '{resource_pattern}' not found",
                        )

                    # Execute the resource function
                    result = await resource_func(**query_params)
                    return {"result": result}
                else:
                    raise HTTPException(
                        status_code=500, detail="MCP module not properly loaded"
                    )

            except Exception as e:
                logger.error(f"Error getting resource {resource_pattern}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/credentials")
        async def update_credentials(credentials: Dict[str, str]):
            """Update server credentials"""
            self.config.update(credentials)
            await self.apply_credentials()
            return {"message": "Credentials updated successfully"}

        @self.app.post("/queue/process")
        async def process_queue():
            """Process jobs from Redis queue"""
            import redis.asyncio as redis

            redis_client = redis.Redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379")
            )

            try:
                # Pop job from queue (blocking for 1 second)
                job_data = await redis_client.blpop(
                    f"mcp_queue:{self.server_type}", timeout=1
                )

                if not job_data:
                    return {"message": "No jobs in queue"}

                job = json.loads(job_data[1])
                tool_name = job["tool_name"]
                parameters = job["parameters"]
                job_id = job["job_id"]

                # Execute the tool
                if not self.mcp_module:
                    await self.load_mcp_module()

                await self.apply_credentials()

                if hasattr(self.mcp_module, "app") and hasattr(
                    self.mcp_module.app, "_tools"
                ):
                    tool_func = self.mcp_module.app._tools.get(tool_name)
                    if tool_func:
                        result = await tool_func(**parameters)

                        # Store result in Redis
                        await redis_client.setex(
                            f"mcp_result:{job_id}",
                            3600,  # 1 hour TTL
                            json.dumps({"result": result, "status": "completed"}),
                        )

                        return {"job_id": job_id, "status": "completed"}
                    else:
                        error_msg = f"Tool '{tool_name}' not found"
                        await redis_client.setex(
                            f"mcp_result:{job_id}",
                            3600,
                            json.dumps({"error": error_msg, "status": "failed"}),
                        )
                        return {
                            "job_id": job_id,
                            "status": "failed",
                            "error": error_msg,
                        }

            except Exception as e:
                logger.error(f"Error processing queue job: {e}")
                if "job_id" in locals():
                    await redis_client.setex(
                        f"mcp_result:{job_id}",
                        3600,
                        json.dumps({"error": str(e), "status": "failed"}),
                    )
                return {"error": str(e)}
            finally:
                await redis_client.close()

    async def load_mcp_module(self):
        """Load the MCP module based on server type"""
        try:
            if self.server_type == "github":
                self.mcp_module = importlib.import_module("cortex.mcp.github_server")
            else:
                raise ValueError(f"Unsupported server type: {self.server_type}")

            logger.info(f"Loaded MCP module for {self.server_type}")
        except Exception as e:
            logger.error(f"Failed to load MCP module for {self.server_type}: {e}")
            raise

    async def apply_credentials(self):
        """Apply credentials to the MCP module"""
        if not self.mcp_module:
            return

        try:
            if self.server_type == "github":
                github_token = self.config.get("github_token") or os.getenv(
                    "GITHUB_TOKEN"
                )
                if github_token:
                    # Create server_data structure for GitHubUtils
                    server_data = {
                        "module": self.mcp_module,
                        "credentials": {"github_token": github_token},
                    }

                    success = GitHubUtils.apply_github_credentials(server_data)
                    if success:
                        logger.info("Applied GitHub credentials")
                    else:
                        logger.warning("Failed to apply GitHub credentials")
        except Exception as e:
            logger.error(f"Failed to apply credentials: {e}")

    async def start(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the MCP server"""
        logger.info(f"Starting {self.server_type} MCP server on {host}:{port}")

        # Load the MCP module
        await self.load_mcp_module()

        # Apply initial credentials
        await self.apply_credentials()

        # Start the server
        config = uvicorn.Config(app=self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


async def main():
    """Main function to run the MCP server"""
    parser = argparse.ArgumentParser(description="Run an independent MCP server")
    parser.add_argument(
        "--server-type", required=True, help="Type of MCP server (github, etc.)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--config", help="JSON config string or file path")

    args = parser.parse_args()

    # Parse config
    config = {}
    if args.config:
        try:
            if os.path.isfile(args.config):
                with open(args.config, "r") as f:
                    config = json.load(f)
            else:
                config = json.loads(args.config)
        except Exception as e:
            logger.error(f"Failed to parse config: {e}")
            sys.exit(1)

    # Add environment variables to config
    if args.server_type == "github":
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            config["github_token"] = github_token

    # Create and start server
    runner = MCPServerRunner(args.server_type, config)
    try:
        await runner.start(args.host, args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
