from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, String, Boolean, Integer, Text, JSON
from sqlalchemy import ForeignKey
from typing import Optional, Dict, Any, List
from datetime import datetime


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    mcp_servers: Mapped[List["MCPServer"]] = relationship(
        "MCPServer", back_populates="user", cascade="all, delete-orphan"
    )
    mcp_preferences: Mapped[Optional["UserMCPPreference"]] = relationship(
        "UserMCPPreference", back_populates="user", cascade="all, delete-orphan"
    )


class Token(Base):
    """Token model for tracking active JWT tokens."""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MCPServer(Base):
    """MCP Server configuration model."""

    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    server_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_path: Mapped[str] = mapped_column(String(255), nullable=False)
    client_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="mcp_servers")
    server_credentials: Mapped[List["MCPServerCredential"]] = relationship(
        "MCPServerCredential", back_populates="mcp_server", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MCPServer(id={self.id}, name='{self.name}', type='{self.server_type}')>"


class MCPServerCredential(Base):
    """MCP Server credential storage model."""

    __tablename__ = "mcp_server_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mcp_server_id: Mapped[int] = mapped_column(Integer, ForeignKey("mcp_servers.id"), nullable=False)
    credential_name: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_value: Mapped[str] = mapped_column(Text, nullable=False)  # Should be encrypted
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    mcp_server: Mapped["MCPServer"] = relationship("MCPServer", back_populates="server_credentials")

    def __repr__(self) -> str:
        return f"<MCPServerCredential(id={self.id}, name='{self.credential_name}')>"


class UserMCPPreference(Base):
    """User preferences for MCP server usage."""

    __tablename__ = "user_mcp_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    default_mcp_server_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mcp_servers.id"), nullable=True
    )
    auto_retry_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="mcp_preferences")
    default_mcp_server: Mapped[Optional["MCPServer"]] = relationship("MCPServer")

    def __repr__(self) -> str:
        return f"<UserMCPPreference(id={self.id}, user_id={self.user_id})>"
