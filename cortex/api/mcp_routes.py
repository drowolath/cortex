from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.database.mcp_service import get_mcp_service, MCPServerService
from ..core.intelligent_agent import (
    process_intelligent_message,
    get_intelligent_agent,
)
from ..core.queue_service import QueueService
from ..core.api_utils import handle_mcp_errors
from .dependencies import get_current_user
from ..core.database.models import User

router = APIRouter(prefix="/mcp", tags=["MCP Servers"])


# Pydantic models
class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    server_type: str = Field(..., min_length=1, max_length=50)
    module_path: str = Field(..., min_length=1, max_length=255)
    client_class: Optional[str] = Field(None, max_length=100)
    config: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    is_enabled: bool = True
    is_default: bool = False


class MCPServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    server_type: Optional[str] = Field(None, min_length=1, max_length=50)
    module_path: Optional[str] = Field(None, min_length=1, max_length=255)
    client_class: Optional[str] = Field(None, max_length=100)
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class MCPServerResponse(BaseModel):
    id: int
    name: str
    server_type: str
    module_path: str
    client_class: Optional[str]
    config: Dict[str, Any]
    description: Optional[str]
    is_enabled: bool
    is_default: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MCPCredentialCreate(BaseModel):
    credential_name: str = Field(..., min_length=1, max_length=100)
    credential_value: str = Field(..., min_length=1)


class MCPCredentialResponse(BaseModel):
    id: int
    credential_name: str
    is_encrypted: bool
    created_at: str

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    default_mcp_server_id: Optional[int] = None
    auto_retry_enabled: bool = True
    max_retry_attempts: int = Field(3, ge=1, le=10)
    timeout_seconds: int = Field(30, ge=5, le=300)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserPreferencesResponse(BaseModel):
    id: int
    default_mcp_server_id: Optional[int]
    auto_retry_enabled: bool
    max_retry_attempts: int
    timeout_seconds: int
    preferences: Dict[str, Any]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    server_id: Optional[int] = None


class IntelligentMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    server_id: Optional[int] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


class MessageResponse(BaseModel):
    response: str
    server_used: Optional[Dict[str, Any]] = None


# Routes
@router.post("/servers", response_model=MCPServerResponse)
async def create_mcp_server(
    server_data: MCPServerCreate,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Create a new MCP server configuration."""
    try:
        mcp_server = await mcp_service.create_mcp_server(
            user_id=current_user.id,
            name=server_data.name,
            server_type=server_data.server_type,
            module_path=server_data.module_path,
            client_class=server_data.client_class,
            config=server_data.config,
            description=server_data.description,
            is_enabled=server_data.is_enabled,
            is_default=server_data.is_default,
        )
        return MCPServerResponse.model_validate(mcp_server)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create MCP server: {str(e)}",
        )


@router.get("/servers", response_model=List[MCPServerResponse])
async def get_mcp_servers(
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Get all MCP servers for the current user."""
    try:
        servers = await mcp_service.get_user_mcp_servers(current_user.id)
        return [MCPServerResponse.model_validate(server) for server in servers]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get MCP servers: {str(e)}",
        )


@router.get("/servers/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Get a specific MCP server."""
    try:
        server = await mcp_service.get_mcp_server(server_id, current_user.id)
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
            )
        return MCPServerResponse.model_validate(server)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get MCP server: {str(e)}",
        )


@router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: int,
    server_data: MCPServerUpdate,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Update an MCP server configuration."""
    try:
        # Filter out None values
        updates = {k: v for k, v in server_data.model_dump().items() if v is not None}

        server = await mcp_service.update_mcp_server(
            server_id, current_user.id, **updates
        )
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
            )
        return MCPServerResponse.model_validate(server)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update MCP server: {str(e)}",
        )


@router.delete("/servers/{server_id}")
async def delete_mcp_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Delete an MCP server configuration."""
    try:
        success = await mcp_service.delete_mcp_server(server_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
            )
        return {"message": "MCP server deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete MCP server: {str(e)}",
        )


@router.post("/servers/{server_id}/credentials", response_model=MCPCredentialResponse)
async def add_server_credential(
    server_id: int,
    credential_data: MCPCredentialCreate,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Add a credential to an MCP server."""
    try:
        credential = await mcp_service.add_server_credential(
            server_id,
            current_user.id,
            credential_data.credential_name,
            credential_data.credential_value,
        )
        return MCPCredentialResponse.model_validate(credential)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add credential: {str(e)}",
        )


@router.get(
    "/servers/{server_id}/credentials", response_model=List[MCPCredentialResponse]
)
async def get_server_credentials(
    server_id: int,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Get credentials for an MCP server (without values for security)."""
    try:
        credentials = await mcp_service.get_server_credentials(
            server_id, current_user.id, decrypt=False
        )
        return [MCPCredentialResponse.model_validate(cred) for cred in credentials]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get credentials: {str(e)}",
        )


@router.get("/servers/default", response_model=Optional[MCPServerResponse])
async def get_default_mcp_server(
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Get the default MCP server for the current user."""
    try:
        server = await mcp_service.get_default_mcp_server(current_user.id)
        if server:
            return MCPServerResponse.model_validate(server)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default MCP server: {str(e)}",
        )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    preferences_data: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Update user MCP preferences."""
    try:
        preferences = await mcp_service.set_user_preferences(
            user_id=current_user.id,
            default_mcp_server_id=preferences_data.default_mcp_server_id,
            auto_retry_enabled=preferences_data.auto_retry_enabled,
            max_retry_attempts=preferences_data.max_retry_attempts,
            timeout_seconds=preferences_data.timeout_seconds,
            preferences=preferences_data.preferences,
        )
        return UserPreferencesResponse.model_validate(preferences)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update preferences: {str(e)}",
        )


@router.get("/preferences", response_model=Optional[UserPreferencesResponse])
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    mcp_service: MCPServerService = Depends(get_mcp_service),
):
    """Get user MCP preferences."""
    try:
        preferences = await mcp_service.get_user_preferences(current_user.id)
        if preferences:
            return UserPreferencesResponse.model_validate(preferences)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preferences: {str(e)}",
        )


@router.get("/servers/available")
async def get_available_servers(current_user: User = Depends(get_current_user)):
    """Get available MCP servers for the current user."""
    try:
        orchestrator = await get_intelligent_agent(current_user.id)
        servers = await orchestrator.get_available_servers()
        return {"servers": servers}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available servers: {str(e)}",
        )


@router.post("/intelligent-process", response_model=MessageResponse)
async def intelligent_process_message(
    request: IntelligentMessageRequest, current_user: User = Depends(get_current_user)
):
    """Process a message using the intelligent agent with LiteLLM."""
    try:
        response = await process_intelligent_message(
            user_id=current_user.id,
            message=request.message,
            server_id=request.server_id,
            conversation_history=request.conversation_history,
        )

        # Get info about which server was used
        agent = await get_intelligent_agent(current_user.id)
        servers = await agent.get_available_servers()

        server_used = None
        if request.server_id:
            server_used = next(
                (s for s in servers if s["id"] == request.server_id), None
            )
        elif servers:
            # Find default server or first available
            server_used = next(
                (s for s in servers if s.get("is_default")),
                servers[0] if servers else None,
            )

        return MessageResponse(response=response, server_used=server_used)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process intelligent message: {str(e)}",
        )


# Queue endpoints
class QueueJobRequest(BaseModel):
    server_type: str
    tool_name: str
    parameters: Dict[str, Any]


class QueueJobResponse(BaseModel):
    job_id: str
    status: str = "queued"


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/queue/enqueue", response_model=QueueJobResponse)
@handle_mcp_errors
async def enqueue_job(
    request: QueueJobRequest, current_user: User = Depends(get_current_user)
):
    """Enqueue a job for asynchronous processing"""
    queue_service = QueueService()
    job_id = await queue_service.enqueue_job(
        server_type=request.server_type,
        tool_name=request.tool_name,
        parameters=request.parameters,
    )
    await queue_service.close()

    return QueueJobResponse(job_id=job_id)


@router.get("/queue/result/{job_id}", response_model=JobResultResponse)
@handle_mcp_errors
async def get_job_result(job_id: str, current_user: User = Depends(get_current_user)):
    """Get job result"""
    queue_service = QueueService()
    result = await queue_service.get_job_result(job_id)
    await queue_service.close()

    if not result:
        return JobResultResponse(job_id=job_id, status="pending")

    return JobResultResponse(
        job_id=job_id,
        status=result.get("status", "unknown"),
        result=result.get("result"),
        error=result.get("error"),
    )
