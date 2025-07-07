from typing import Dict, List, Optional, Any
from .mcp_base_service import MCPBaseService
from .github_utils import GitHubUtils
from .logger import get_logger

logger = get_logger(__name__)


class UserAgentOrchestrator(MCPBaseService):
    """
    Agent orchestrator that uses user-configured MCP servers from the database.
    """

    def __init__(self, user_id: int):
        super().__init__(user_id)

    async def initialize(self):
        """Initialize the orchestrator with user's MCP servers."""
        await super().initialize()
        logger.info(f"User Agent Orchestrator initialized for user {self.user_id}")

    async def process_message(
        self, message: str, server_id: Optional[int] = None
    ) -> str:
        """
        Process a message using the specified server or default server.

        Args:
            message: The message string to process
            server_id: Optional specific server ID, otherwise uses default

        Returns:
            Response string from the MCP server
        """
        if not self._initialized:
            await self.initialize()

        # Get target server
        target_server = await self._get_target_server(server_id)
        if not target_server:
            return self._get_no_server_error_message()

        server_config = target_server["config"]

        try:
            if server_config.server_type == "github":
                return await self._process_github_message(message, target_server)
            else:
                return await self._process_generic_message(message, target_server)
        except Exception as e:
            logger.error(
                f"Error processing message with server {server_config.name}: {e}"
            )
            return f"Error: {str(e)}"

    async def _get_target_server(
        self, server_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Get the target server to use for processing."""
        target_server = await super()._get_target_server(server_id)
        if target_server:
            return target_server

        # Fall back to database default server lookup for user agent
        default_server = await self.mcp_service.get_default_mcp_server(self.user_id)
        if default_server and default_server.id in self.loaded_servers:
            return self.loaded_servers[default_server.id]

        return None

    async def _process_github_message(
        self, message: str, server_info: Dict[str, Any]
    ) -> str:
        """Process message using GitHub MCP server."""
        module = server_info["module"]
        config = server_info["config"]
        credentials = server_info["credentials"]

        # Apply GitHub credentials
        GitHubUtils.apply_github_credentials(server_info)

        message = message.strip().lower()

        # Simple keyword-based routing (same as before)
        if "repo info" in message or "repository info" in message:
            parts = message.split()
            repo_part = None
            for part in parts:
                if "/" in part:
                    repo_part = part
                    break

            if repo_part:
                owner, repo = repo_part.split("/", 1)
                return await module.get_repository_info(owner, repo)
            else:
                return "Please specify repository in format 'owner/repo'"

        elif "list issues" in message:
            parts = message.split()
            repo_part = None
            for part in parts:
                if "/" in part:
                    repo_part = part
                    break

            if repo_part:
                owner, repo = repo_part.split("/", 1)
                return await module.list_issues(owner, repo)
            else:
                return "Please specify repository in format 'owner/repo'"

        elif "list contents" in message or "show contents" in message:
            parts = message.split()
            repo_part = None
            for part in parts:
                if "/" in part:
                    repo_part = part
                    break

            if repo_part:
                owner, repo = repo_part.split("/", 1)
                return await module.list_repository_contents(owner, repo)
            else:
                return "Please specify repository in format 'owner/repo'"

        elif "get file" in message or "show file" in message:
            parts = message.split()
            repo_part = None
            file_part = None

            for part in parts:
                if "/" in part and "." not in part:  # likely repo
                    repo_part = part
                elif "/" in part and "." in part:  # likely file
                    file_part = part

            if repo_part and file_part:
                owner, repo = repo_part.split("/", 1)
                return await module.get_file_content(owner, repo, file_part)
            else:
                return "Please specify repository (owner/repo) and file path"

        elif "search repo" in message or "search repository" in message:
            query_start = message.find("search repo") + len("search repo")
            if query_start == -1:
                query_start = message.find("search repository") + len(
                    "search repository"
                )

            query = message[query_start:].strip()
            if query:
                return await module.search_repositories(query)
            else:
                return "Please specify search query"

        elif "list prs" in message or "list pull requests" in message:
            parts = message.split()
            repo_part = None
            for part in parts:
                if "/" in part:
                    repo_part = part
                    break

            if repo_part:
                owner, repo = repo_part.split("/", 1)
                return await module.list_pull_requests(owner, repo)
            else:
                return "Please specify repository in format 'owner/repo'"

        else:
            return self._get_github_help_message()

    async def _process_generic_message(
        self, message: str, server_info: Dict[str, Any]
    ) -> str:
        """Process message using a generic MCP server."""
        module = server_info["module"]
        config = server_info["config"]

        # This would need to be implemented based on the specific MCP server type
        return f"Generic MCP server processing not yet implemented for {config.server_type}"

    def _get_github_help_message(self) -> str:
        """Return help message for GitHub commands."""
        return """
**Available GitHub Commands:**

- `repo info owner/repo` - Get repository information
- `list contents owner/repo` - List repository contents  
- `get file owner/repo path/to/file` - Get file content
- `list issues owner/repo` - List repository issues
- `list prs owner/repo` - List pull requests
- `search repo query` - Search repositories

**Examples:**
- `repo info microsoft/vscode`
- `list issues kamino-labs/cortex`
- `get file microsoft/vscode README.md`
- `search repo python web framework`
"""

    async def get_available_servers(self) -> List[Dict[str, Any]]:
        """Get list of available MCP servers for the user."""
        return await super().get_available_servers()

    async def reload_servers(self):
        """Reload user's MCP servers from database."""
        self.loaded_servers.clear()
        await self._load_user_servers()
        logger.info(f"Reloaded MCP servers for user {self.user_id}")


# Factory function
async def get_user_orchestrator(user_id: int) -> UserAgentOrchestrator:
    """Get a UserAgentOrchestrator for a specific user."""
    orchestrator = UserAgentOrchestrator(user_id)
    await orchestrator.initialize()
    return orchestrator


# Convenience function for processing messages
async def process_user_message(
    user_id: int, message: str, server_id: Optional[int] = None
) -> str:
    """
    Process a message for a specific user using their configured MCP servers.

    Args:
        user_id: The user ID
        message: The message string to process
        server_id: Optional specific server ID to use

    Returns:
        Response string from the MCP server
    """
    orchestrator = await get_user_orchestrator(user_id)
    return await orchestrator.process_message(message, server_id)
