from typing import Dict, Any, Optional
from .logger import get_logger

logger = get_logger(__name__)


class GitHubUtils:
    """Utility class for GitHub operations and credential management."""

    @staticmethod
    def apply_github_credentials(server_data: Dict[str, Any]) -> bool:
        """
        Apply GitHub credentials to a server module.

        Args:
            server_data: Server data containing module and credentials

        Returns:
            True if credentials were applied successfully, False otherwise
        """
        try:
            github_token = server_data["credentials"].get("github_token")
            if not github_token:
                logger.warning("No GitHub token found in credentials")
                return False

            module = server_data["module"]

            # Apply token to module if it has the appropriate attributes
            if hasattr(module, "set_github_token"):
                module.set_github_token(github_token)
                logger.info("Applied GitHub token via set_github_token method")
                return True
            elif hasattr(module, "github_client"):
                module.github_client.token = github_token
                module.github_client.headers["Authorization"] = f"token {github_token}"
                logger.info("Applied GitHub token to github_client")
                return True
            else:
                logger.warning("Module does not have expected GitHub token attributes")
                return False

        except Exception as e:
            logger.error(f"Failed to apply GitHub credentials: {e}")
            return False

    @staticmethod
    def parse_github_repo_info(message: str) -> Optional[Dict[str, str]]:
        """
        Parse GitHub repository information from a message.

        Args:
            message: Message containing GitHub repository information

        Returns:
            Dictionary with 'owner' and 'repo' keys, or None if not found
        """
        try:
            # Look for GitHub URL patterns
            if "github.com" in message.lower():
                parts = message.split("github.com/")
                if len(parts) > 1:
                    repo_part = parts[1].split("/")
                    if len(repo_part) >= 2:
                        owner = repo_part[0]
                        repo = repo_part[1].split()[0].strip(".,!?")
                        return {"owner": owner, "repo": repo}

            # Look for owner/repo pattern
            words = message.split()
            for word in words:
                if "/" in word and len(word.split("/")) == 2:
                    parts = word.split("/")
                    if all(part.strip() for part in parts):
                        return {"owner": parts[0], "repo": parts[1]}

            return None

        except Exception as e:
            logger.error(f"Failed to parse GitHub repo info: {e}")
            return None

    @staticmethod
    def extract_github_keywords(message: str) -> Dict[str, Any]:
        """
        Extract GitHub-related keywords and context from a message.

        Args:
            message: Input message to analyze

        Returns:
            Dictionary containing extracted keywords and context
        """
        message_lower = message.lower()
        keywords = {
            "action": None,
            "target": None,
            "repo_info": None,
            "additional_params": {},
        }

        # Determine action
        if any(word in message_lower for word in ["list", "show", "get"]):
            if "issue" in message_lower:
                keywords["action"] = "list_issues"
            elif "pr" in message_lower or "pull request" in message_lower:
                keywords["action"] = "list_prs"
            elif "content" in message_lower or "file" in message_lower:
                keywords["action"] = "list_contents"
            elif "repo" in message_lower or "repository" in message_lower:
                keywords["action"] = "get_repo"
        elif any(word in message_lower for word in ["create", "make", "add"]):
            if "issue" in message_lower:
                keywords["action"] = "create_issue"
        elif any(word in message_lower for word in ["read", "view", "open"]):
            if "file" in message_lower:
                keywords["action"] = "get_file"

        # Extract repository information
        repo_info = GitHubUtils.parse_github_repo_info(message)
        if repo_info:
            keywords["repo_info"] = repo_info

        return keywords
