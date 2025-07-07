import os
import asyncio
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import httpx
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ImageContent, EmbeddedResource

app = FastMCP("GitHub MCP Server")

class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Cortex-GitHub-MCP-Server/1.0"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the GitHub API"""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=self.headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

    async def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information"""
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
        """Get repository contents"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}" if path else f"/repos/{owner}/{repo}/contents"
        return await self._request("GET", endpoint)

    async def get_file_content(self, owner: str, repo: str, path: str) -> Dict[str, Any]:
        """Get file content"""
        return await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}")

    async def list_issues(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """List repository issues"""
        return await self._request("GET", f"/repos/{owner}/{repo}/issues", params={"state": state})

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get a specific issue"""
        return await self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")

    async def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """List repository pull requests"""
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls", params={"state": state})

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Get a specific pull request"""
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")

    async def create_issue(self, owner: str, repo: str, title: str, body: str = "", labels: List[str] = None) -> Dict[str, Any]:
        """Create a new issue"""
        data = {
            "title": title,
            "body": body
        }
        if labels:
            data["labels"] = labels
        return await self._request("POST", f"/repos/{owner}/{repo}/issues", json=data)

    async def search_repositories(self, query: str, sort: str = "stars", order: str = "desc") -> Dict[str, Any]:
        """Search for repositories"""
        return await self._request("GET", "/search/repositories", params={
            "q": query,
            "sort": sort,
            "order": order
        })

github_client = GitHubClient()

@app.tool()
async def get_repository_info(owner: str, repo: str) -> str:
    """Get detailed information about a GitHub repository"""
    try:
        repo_info = await github_client.get_repo_info(owner, repo)
        return f"""Repository: {repo_info['full_name']}
Description: {repo_info['description']}
Stars: {repo_info['stargazers_count']}
Forks: {repo_info['forks_count']}
Language: {repo_info['language']}
Created: {repo_info['created_at']}
Last Updated: {repo_info['updated_at']}
Clone URL: {repo_info['clone_url']}
"""
    except Exception as e:
        return f"Error getting repository info: {str(e)}"

@app.tool()
async def list_repository_contents(owner: str, repo: str, path: str = "") -> str:
    """List the contents of a GitHub repository or directory"""
    try:
        contents = await github_client.get_repo_contents(owner, repo, path)
        result = f"Contents of {owner}/{repo}/{path}:\n\n"
        for item in contents:
            item_type = "📁" if item['type'] == 'dir' else "📄"
            result += f"{item_type} {item['name']} ({item['type']})\n"
        return result
    except Exception as e:
        return f"Error listing repository contents: {str(e)}"

@app.tool()
async def get_file_content(owner: str, repo: str, file_path: str) -> str:
    """Get the content of a specific file from a GitHub repository"""
    try:
        file_info = await github_client.get_file_content(owner, repo, file_path)
        if file_info['encoding'] == 'base64':
            import base64
            content = base64.b64decode(file_info['content']).decode('utf-8')
            return f"File: {file_path}\nSize: {file_info['size']} bytes\n\n{content}"
        else:
            return f"File: {file_path}\nContent encoding not supported: {file_info['encoding']}"
    except Exception as e:
        return f"Error getting file content: {str(e)}"

@app.tool()
async def list_issues(owner: str, repo: str, state: str = "open") -> str:
    """List issues in a GitHub repository"""
    try:
        issues = await github_client.list_issues(owner, repo, state)
        result = f"Issues in {owner}/{repo} (state: {state}):\n\n"
        for issue in issues:
            result += f"#{issue['number']}: {issue['title']}\n"
            result += f"  State: {issue['state']}\n"
            result += f"  Author: {issue['user']['login']}\n"
            result += f"  Created: {issue['created_at']}\n\n"
        return result
    except Exception as e:
        return f"Error listing issues: {str(e)}"

@app.tool()
async def get_issue_details(owner: str, repo: str, issue_number: int) -> str:
    """Get detailed information about a specific GitHub issue"""
    try:
        issue = await github_client.get_issue(owner, repo, issue_number)
        result = f"Issue #{issue['number']}: {issue['title']}\n\n"
        result += f"State: {issue['state']}\n"
        result += f"Author: {issue['user']['login']}\n"
        result += f"Created: {issue['created_at']}\n"
        result += f"Updated: {issue['updated_at']}\n\n"
        result += f"Description:\n{issue['body']}\n\n"
        if issue['labels']:
            result += f"Labels: {', '.join([label['name'] for label in issue['labels']])}\n"
        return result
    except Exception as e:
        return f"Error getting issue details: {str(e)}"

@app.tool()
async def list_pull_requests(owner: str, repo: str, state: str = "open") -> str:
    """List pull requests in a GitHub repository"""
    try:
        prs = await github_client.list_pull_requests(owner, repo, state)
        result = f"Pull Requests in {owner}/{repo} (state: {state}):\n\n"
        for pr in prs:
            result += f"#{pr['number']}: {pr['title']}\n"
            result += f"  State: {pr['state']}\n"
            result += f"  Author: {pr['user']['login']}\n"
            result += f"  Created: {pr['created_at']}\n"
            result += f"  Branch: {pr['head']['ref']} -> {pr['base']['ref']}\n\n"
        return result
    except Exception as e:
        return f"Error listing pull requests: {str(e)}"

@app.tool()
async def get_pull_request_details(owner: str, repo: str, pr_number: int) -> str:
    """Get detailed information about a specific GitHub pull request"""
    try:
        pr = await github_client.get_pull_request(owner, repo, pr_number)
        result = f"Pull Request #{pr['number']}: {pr['title']}\n\n"
        result += f"State: {pr['state']}\n"
        result += f"Author: {pr['user']['login']}\n"
        result += f"Created: {pr['created_at']}\n"
        result += f"Updated: {pr['updated_at']}\n"
        result += f"Branch: {pr['head']['ref']} -> {pr['base']['ref']}\n\n"
        result += f"Description:\n{pr['body']}\n\n"
        result += f"Mergeable: {pr['mergeable']}\n"
        result += f"Commits: {pr['commits']}\n"
        result += f"Additions: {pr['additions']}\n"
        result += f"Deletions: {pr['deletions']}\n"
        result += f"Changed Files: {pr['changed_files']}\n"
        return result
    except Exception as e:
        return f"Error getting pull request details: {str(e)}"

@app.tool()
async def create_issue(owner: str, repo: str, title: str, body: str = "", labels: List[str] = None) -> str:
    """Create a new issue in a GitHub repository"""
    try:
        issue = await github_client.create_issue(owner, repo, title, body, labels)
        return f"Created issue #{issue['number']}: {issue['title']}\nURL: {issue['html_url']}"
    except Exception as e:
        return f"Error creating issue: {str(e)}"

@app.tool()
async def search_repositories(query: str, sort: str = "stars", order: str = "desc") -> str:
    """Search for GitHub repositories"""
    try:
        results = await github_client.search_repositories(query, sort, order)
        result = f"Found {results['total_count']} repositories for '{query}':\n\n"
        for repo in results['items'][:10]:  # Limit to first 10 results
            result += f"{repo['full_name']}\n"
            result += f"  Description: {repo['description']}\n"
            result += f"  Stars: {repo['stargazers_count']}\n"
            result += f"  Language: {repo['language']}\n"
            result += f"  URL: {repo['html_url']}\n\n"
        return result
    except Exception as e:
        return f"Error searching repositories: {str(e)}"

@app.resource("github://repo/{owner}/{repo}")
async def get_repo_resource(owner: str, repo: str) -> str:
    """Get repository information as a resource"""
    return await get_repository_info(owner, repo)

@app.resource("github://repo/{owner}/{repo}/file/{file_path}")
async def get_file_resource(owner: str, repo: str, file_path: str) -> str:
    """Get file content as a resource"""
    return await get_file_content(owner, repo, file_path)

@app.resource("github://repo/{owner}/{repo}/issues")
async def get_issues_resource(owner: str, repo: str) -> str:
    """Get repository issues as a resource"""
    return await list_issues(owner, repo)

@app.resource("github://repo/{owner}/{repo}/pulls")
async def get_pulls_resource(owner: str, repo: str) -> str:
    """Get repository pull requests as a resource"""
    return await list_pull_requests(owner, repo)

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())