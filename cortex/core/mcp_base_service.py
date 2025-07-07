import importlib
from typing import Dict, List, Optional, Any
from .database.mcp_service import get_mcp_service, MCPServerService
from .logger import get_logger

logger = get_logger(__name__)


class MCPBaseService:
    """
    Base service for MCP server management and common operations.
    Provides shared functionality for user agent orchestrators.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.mcp_service: Optional[MCPServerService] = None
        self.loaded_servers: Dict[int, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize the service with user's MCP servers."""
        if self._initialized:
            return

        self.mcp_service = await get_mcp_service()
        await self._load_user_servers()
        self._initialized = True
        logger.info(f"MCP Base Service initialized for user {self.user_id}")

    async def _load_user_servers(self):
        """Load user's enabled MCP servers."""
        if not self.mcp_service:
            return

        servers = await self.mcp_service.get_user_mcp_servers(self.user_id)
        enabled_servers = [s for s in servers if s.is_enabled]

        for server in enabled_servers:
            try:
                module = importlib.import_module(server.module_path)
                self.loaded_servers[server.id] = {
                    "module": module,
                    "config": server,
                    "credentials": await self._load_server_credentials(server.id),
                }
                logger.info(f"Loaded MCP server: {server.name} (ID: {server.id})")
            except Exception as e:
                logger.error(f"Failed to load MCP server {server.name}: {e}")

    async def _load_server_credentials(self, server_id: int) -> Dict[str, str]:
        """Load and decrypt credentials for a server."""
        try:
            credentials = await self.mcp_service.get_server_credentials(
                server_id, self.user_id, decrypt=True
            )
            return {cred.credential_name: cred.credential_value for cred in credentials}
        except Exception as e:
            logger.error(f"Failed to load credentials for server {server_id}: {e}")
            return {}

    async def _get_target_server(
        self, server_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Get target server by ID or default server."""
        if not self.loaded_servers:
            return None

        if server_id and server_id in self.loaded_servers:
            return self.loaded_servers[server_id]

        default_server = next(
            (s for s in self.loaded_servers.values() if s["config"].is_default),
            None,
        )
        if default_server:
            return default_server

        return next(iter(self.loaded_servers.values()), None)

    async def get_available_servers(self) -> List[Dict[str, Any]]:
        """List available MCP servers for the user."""
        if not self._initialized:
            await self.initialize()

        servers = []
        for server_id, server_data in self.loaded_servers.items():
            config = server_data["config"]
            servers.append(
                {
                    "id": server_id,
                    "name": config.name,
                    "type": config.server_type,
                    "is_default": config.is_default,
                    "description": config.description,
                }
            )
        return servers

    def _ensure_initialized(self):
        """Ensure the service is initialized."""
        if not self._initialized:
            raise RuntimeError("Service not initialized. Call initialize() first.")

    def _get_no_server_error_message(self) -> str:
        """Get error message when no server is available."""
        available_servers = list(self.loaded_servers.keys())
        return f"Error: No MCP server available. Loaded servers: {available_servers}"
