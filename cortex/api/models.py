from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChainlitMessage(BaseModel):
    """Model for messages received from Chainlit."""
    
    id: str = Field(..., description="Unique message identifier")
    content: str = Field(..., description="Message content")
    author: str = Field(..., description="Message author")
    timestamp: Optional[datetime] = Field(default=None, description="Message timestamp")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class LLMRequest(BaseModel):
    """Model for LLM processing requests."""
    
    message: str = Field(..., description="Message to process")
    model: str = Field(default="gpt-3.5-turbo", description="LLM model to use")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens")
    temperature: Optional[float] = Field(default=None, description="Temperature setting")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class LLMResponse(BaseModel):
    """Model for LLM processing responses."""
    
    id: str = Field(..., description="Response identifier")
    content: str = Field(..., description="LLM response content")
    model: str = Field(..., description="Model used")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ErrorResponse(BaseModel):
    """Model for error responses."""
    
    error: str = Field(..., description="Error message")
    code: int = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


class LoginRequest(BaseModel):
    """Model for login requests."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    """Model for login responses."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class User(BaseModel):
    """User model."""
    username: str = Field(..., description="Username")
    is_active: bool = Field(default=True, description="Whether user is active")