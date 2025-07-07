from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..core.litellm import prompt_llm
from ..core.intelligent_agent import process_intelligent_message
from ..core.database.manager import get_db
from ..core.auth import get_auth_service
from .models import (
    ChainlitMessage,
    LLMRequest,
    LLMResponse,
    LoginRequest,
    LoginResponse,
    User,
)
from .dependencies import get_current_user, security
from . import mcp_routes

from .startup import lifespan

logger = get_logger("api")

app = FastAPI(
    title="Cortex API",
    description="API for coordinating agentic workflows across your MCP universe",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware, for now I'll simply allow all origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include MCP routes
app.include_router(mcp_routes.router)


@app.get("/")
async def root():
    """Very simple health check."""
    return {"message": "Cortex API is running", "timestamp": datetime.now()}


@app.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    auth_service=Depends(get_auth_service),
):
    token = await auth_service.login(db, request.username, request.password)
    return token


@app.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@app.post("/auth/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    auth_service=Depends(get_auth_service),
):
    """Logout user by revoking token."""
    result = await auth_service.logout(db, credentials.credentials)
    return {"message": "Logged out successfully"}


@app.post("/chainlit/message", response_model=LLMResponse)
async def receive_chainlit_message(
    message: ChainlitMessage,
    current_user: User = Depends(get_current_user),
):
    """
    Receive a message from Chainlit and process it through the intelligent agent.
    """
    try:
        logger.info(
            f"Received message from Chainlit: {message.id} (user: {current_user.username})"
        )

        # Process the message through the intelligent agent
        agent_response = await process_intelligent_message(
            user_id=current_user.id,
            message=message.content,
            use_llm=True
        )

        # Create response
        response = LLMResponse(
            id=str(uuid.uuid4()),
            content=agent_response,
            model="intelligent-agent",
            session_id=message.session_id,
            metadata={
                "original_message_id": message.id,
                "author": message.author,
                "processed_by": current_user.username,
                "processed_at": datetime.now().isoformat(),
                "agent_type": "intelligent",
            },
        )

        logger.info(
            f"Successfully processed Chainlit message {message.id} for user {current_user.username}"
        )
        return response

    except Exception as e:
        logger.error(f"Error processing Chainlit message {message.id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing message: {str(e)}"
        )


@app.post("/llm/prompt", response_model=LLMResponse)
async def prompt_llm_endpoint(
    request: LLMRequest, current_user: User = Depends(get_current_user)
):
    """
    Direct endpoint to prompt LLM with a message.

    Args:
        request: LLMRequest containing the message and parameters

    Returns:
        LLMResponse containing the LLM result
    """
    try:
        logger.info(
            f"Processing LLM request for session: {request.session_id} (user: {current_user.username})"
        )

        # Process the message through LiteLLM
        llm_response = prompt_llm(request.message, request.model)

        # Create response
        response = LLMResponse(
            id=str(uuid.uuid4()),
            content=llm_response,
            model=request.model,
            session_id=request.session_id,
            metadata={
                **(request.metadata or {}),
                "processed_by": current_user.username,
                "processed_at": datetime.now().isoformat(),
            },
        )

        logger.info(
            f"Successfully processed LLM request for session: {request.session_id} (user: {current_user.username})"
        )
        return response

    except Exception as e:
        logger.error(f"Error processing LLM request: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing LLM request: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(), "service": "cortex-api"}
