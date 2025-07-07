import json
from typing import Dict, List, Optional, Any
from .mcp_base_service import MCPBaseService
from .github_utils import GitHubUtils
from .litellm import prompt_llm
from .logger import get_logger

logger = get_logger(__name__)


class IntelligentUserAgent(MCPBaseService):
    """
    Enhanced agent orchestrator that uses LiteLLM for intelligent message processing
    and tool selection, combined with user-configured MCP servers.
    """

    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt for LiteLLM."""
        return """You are an intelligent agent orchestrator that helps users interact with various MCP (Model Context Protocol) servers.

Your capabilities include:
1. Analyzing user messages to determine intent and required actions
2. Selecting the appropriate MCP server and tools
3. Extracting parameters from natural language
4. Providing helpful responses

When a user asks something, you should:
1. Identify what they want to do
2. Determine if it requires an MCP server action
3. Extract the necessary parameters
4. Choose the best approach

For GitHub operations, you can:
- Get repository information
- List issues, pull requests, repository contents
- Get file contents
- Search repositories
- Create issues

Always respond in a helpful, concise manner. If you need to call an MCP tool, provide the tool name and parameters in a structured format."""

    async def initialize(self):
        """Initialize the orchestrator with user's MCP servers."""
        await super().initialize()
        logger.info(f"Intelligent User Agent initialized for user {self.user_id}")

    async def process_message(
        self, message: str, server_id: Optional[int] = None, use_llm: bool = True
    ) -> str:
        """
        Process a message using LiteLLM for intelligence and MCP servers for actions.

        Args:
            message: The user message
            server_id: Optional specific server ID
            use_llm: Whether to use LiteLLM for processing (default: True)

        Returns:
            Response string
        """
        if not self._initialized:
            await self.initialize()

        if not use_llm:
            # Fallback to simple keyword-based processing
            return await self._process_simple_message(message, server_id)

        try:
            # First, use LiteLLM to understand the message and determine action
            analysis = await self._analyze_message(message)

            # If LiteLLM suggests an MCP action, execute it
            if analysis.get("requires_mcp_action"):
                return await self._execute_mcp_action(analysis, server_id)
            else:
                # Return LiteLLM's direct response
                return analysis.get("response", "I'm not sure how to help with that.")

        except Exception as e:
            logger.error(f"Error in intelligent processing: {e}")
            # Fallback to simple processing
            return await self._process_simple_message(message, server_id)

    async def _analyze_message(self, message: str) -> Dict[str, Any]:
        """Use LiteLLM to analyze the user message and determine next steps."""

        # Build context about available servers
        server_context = await self._build_server_context()

        analysis_prompt = f"""
{self.system_prompt}

Available MCP servers and capabilities:
{server_context}

User message: "{message}"

Analyze this message and respond with a JSON object containing:
1. "intent": What the user wants to do
2. "requires_mcp_action": true/false - whether this needs an MCP server call
3. "server_type": which type of MCP server to use (if needed)
4. "tool_name": specific tool/function to call (if needed)
5. "parameters": extracted parameters for the tool (if needed)
6. "response": direct response if no MCP action needed

Examples:
- "Show me info about microsoft/vscode repo" -> {{"intent": "get_repo_info", "requires_mcp_action": true, "server_type": "github", "tool_name": "get_repository_info", "parameters": {{"owner": "microsoft", "repo": "vscode"}}}}
- "Hello" -> {{"intent": "greeting", "requires_mcp_action": false, "response": "Hello! I can help you with GitHub operations and other MCP server tasks. What would you like to do?"}}

Respond only with valid JSON:
"""

        try:
            llm_response = prompt_llm(analysis_prompt)

            # Try to parse JSON response
            if llm_response.startswith("```json"):
                llm_response = (
                    llm_response.replace("```json", "").replace("```", "").strip()
                )

            analysis = json.loads(llm_response)
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LiteLLM JSON response: {e}")
            # Return a fallback analysis
            return {
                "intent": "unknown",
                "requires_mcp_action": False,
                "response": llm_response,  # Use raw LLM response as fallback
            }

    async def _build_server_context(self) -> str:
        """Build context string about available MCP servers."""
        if not self.loaded_servers:
            return "No MCP servers available."

        context = []
        for server_id, server_info in self.loaded_servers.items():
            config = server_info["config"]
            if config.server_type == "github":
                context.append(
                    f"- GitHub Server ({config.name}): get_repository_info, list_issues, list_repository_contents, get_file_content, search_repositories, list_pull_requests, create_issue"
                )
            else:
                context.append(
                    f"- {config.server_type} Server ({config.name}): {config.description or 'Generic MCP server'}"
                )

        return "\n".join(context)

    async def _execute_mcp_action(
        self, analysis: Dict[str, Any], server_id: Optional[int] = None
    ) -> str:
        """Execute the MCP action suggested by LiteLLM."""
        tool_name = analysis.get("tool_name")
        parameters = analysis.get("parameters", {})
        server_type = analysis.get("server_type")

        # Find appropriate server
        target_server = await self._find_server_by_type(server_type, server_id)
        if not target_server:
            return f"No {server_type} server available. Please configure one first."

        server_config = target_server["config"]

        try:
            if server_config.server_type == "github":
                return await self._execute_github_action(
                    tool_name, parameters, target_server
                )
            else:
                return f"MCP server type '{server_config.server_type}' execution not yet implemented."

        except Exception as e:
            logger.error(f"Error executing MCP action: {e}")
            return f"Error executing {tool_name}: {str(e)}"

    async def _find_server_by_type(
        self, server_type: str, server_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Find a server by type, optionally by specific ID."""
        if server_id and server_id in self.loaded_servers:
            return self.loaded_servers[server_id]

        # Find by type
        for server_info in self.loaded_servers.values():
            if server_info["config"].server_type == server_type:
                return server_info

        # Try default server
        default_server = await self.mcp_service.get_default_mcp_server(self.user_id)
        if default_server and default_server.id in self.loaded_servers:
            return self.loaded_servers[default_server.id]

        return None

    async def _execute_github_action(
        self, tool_name: str, parameters: Dict[str, Any], server_info: Dict[str, Any]
    ) -> str:
        """Execute a GitHub MCP action."""
        module = server_info["module"]

        # Apply credentials
        GitHubUtils.apply_github_credentials(server_info)

        # Map tool names to module functions
        tool_mapping = {
            "get_repository_info": module.get_repository_info,
            "list_issues": module.list_issues,
            "list_repository_contents": module.list_repository_contents,
            "get_file_content": module.get_file_content,
            "search_repositories": module.search_repositories,
            "list_pull_requests": module.list_pull_requests,
            "create_issue": module.create_issue,
        }

        if tool_name not in tool_mapping:
            return f"Unknown GitHub tool: {tool_name}"

        tool_function = tool_mapping[tool_name]

        try:
            result = await tool_function(**parameters)
            return result
        except Exception as e:
            return f"Error calling {tool_name}: {str(e)}"

    async def _process_simple_message(
        self, message: str, server_id: Optional[int] = None
    ) -> str:
        """Fallback to simple keyword-based processing."""
        # This is the same logic as in user_agent.py
        target_server = await self._get_target_server(server_id)
        if not target_server:
            return "No MCP server available."

        server_config = target_server["config"]

        if server_config.server_type == "github":
            return await self._process_github_message_simple(message, target_server)
        else:
            return f"Simple processing for {server_config.server_type} not implemented."

    async def _process_github_message_simple(
        self, message: str, server_info: Dict[str, Any]
    ) -> str:
        """Simple GitHub message processing (keyword-based)."""
        module = server_info["module"]

        # Apply credentials
        GitHubUtils.apply_github_credentials(server_info)

        message = message.strip().lower()

        # Simple keyword matching (same as original)
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

        # Add other simple patterns...

        return "I'm not sure how to help with that. Try asking about GitHub repositories, issues, or files."

    async def _get_target_server(
        self, server_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Get target server."""
        target_server = await super()._get_target_server(server_id)
        if target_server:
            return target_server

        # Fall back to database default server lookup
        default_server = await self.mcp_service.get_default_mcp_server(self.user_id)
        if default_server and default_server.id in self.loaded_servers:
            return self.loaded_servers[default_server.id]

        return None

    async def chat_with_context(
        self, message: str, conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Chat with the agent using conversation context.

        Args:
            message: Current user message
            conversation_history: Previous messages [{"role": "user|assistant", "content": "..."}]

        Returns:
            Response string
        """
        if not self._initialized:
            await self.initialize()

        # Build conversation context
        context = self.system_prompt + "\n\n"
        context += await self._build_server_context() + "\n\n"

        if conversation_history:
            context += "Conversation history:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages
                context += f"{msg['role']}: {msg['content']}\n"
            context += "\n"

        context += f"User: {message}\nAssistant:"

        try:
            # Use LiteLLM for contextual response
            response = prompt_llm(context)

            # Check if the response suggests an MCP action
            if "```json" in response:
                # Try to parse and execute action
                try:
                    json_start = response.find("```json") + 7
                    json_end = response.find("```", json_start)
                    if json_end > json_start:
                        action_json = response[json_start:json_end].strip()
                        action = json.loads(action_json)

                        if action.get("requires_mcp_action"):
                            mcp_result = await self._execute_mcp_action(action)
                            # Combine LLM response with MCP result
                            text_response = (
                                response[: json_start - 7] + response[json_end + 3 :]
                            )
                            return f"{text_response.strip()}\n\n{mcp_result}"
                except:
                    pass  # If parsing fails, just return the LLM response

            return response

        except Exception as e:
            logger.error(f"Error in contextual chat: {e}")
            return await self.process_message(message, use_llm=False)

    async def get_available_servers(self) -> List[Dict[str, Any]]:
        """Get list of available MCP servers for the user."""
        return await super().get_available_servers()


# Factory functions
async def get_intelligent_agent(user_id: int) -> IntelligentUserAgent:
    """Get an IntelligentUserAgent for a specific user."""
    agent = IntelligentUserAgent(user_id)
    await agent.initialize()
    return agent


async def process_intelligent_message(
    user_id: int,
    message: str,
    server_id: Optional[int] = None,
    use_llm: bool = True,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Process a message using the intelligent agent.

    Args:
        user_id: The user ID
        message: The message string to process
        server_id: Optional specific server ID to use
        use_llm: Whether to use LiteLLM for intelligence
        conversation_history: Optional conversation context

    Returns:
        Response string
    """
    agent = await get_intelligent_agent(user_id)

    if conversation_history:
        return await agent.chat_with_context(message, conversation_history)
    else:
        return await agent.process_message(message, server_id, use_llm)
