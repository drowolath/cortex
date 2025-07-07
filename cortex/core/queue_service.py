import os
import uuid
import json
from typing import Dict, Any, Optional
import redis.asyncio as redis
from .logger import get_logger

logger = get_logger(__name__)


class QueueService:
    """Simple Redis-based queue service for MCP servers"""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None

    async def connect(self):
        """Connect to Redis"""
        if not self.redis_client:
            self.redis_client = redis.Redis.from_url(self.redis_url)

    async def enqueue_job(
        self, server_type: str, tool_name: str, parameters: Dict[str, Any]
    ) -> str:
        """Enqueue a job for processing"""
        await self.connect()

        job_id = str(uuid.uuid4())
        job_data = {"job_id": job_id, "tool_name": tool_name, "parameters": parameters}

        queue_key = f"mcp_queue:{server_type}"
        await self.redis_client.rpush(queue_key, json.dumps(job_data))

        logger.info(f"Enqueued job {job_id} for {server_type}")
        return job_id

    async def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job result from Redis"""
        await self.connect()

        result_key = f"mcp_result:{job_id}"
        result_data = await self.redis_client.get(result_key)

        if result_data:
            return json.loads(result_data)
        return None

    async def wait_for_result(
        self, job_id: str, timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Wait for job result with timeout"""
        import asyncio

        for _ in range(timeout):
            result = await self.get_job_result(job_id)
            if result:
                return result
            await asyncio.sleep(1)

        return None

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
