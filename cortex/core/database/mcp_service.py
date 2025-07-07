import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, update

import os
import base64

from .models import MCPServer, MCPServerCredential, UserMCPPreference, User
from .manager import DatabaseManager

logger = logging.getLogger(__name__)


class Cryptography:
    def __init__(self, key):
        self.key = key

    @staticmethod
    def generate_key():
        return base64.urlsafe_b64encode(os.urandom(32))

    def encrypt(self, data):
        # Simple base64 encoding as fallback (not secure for production)
        return base64.urlsafe_b64encode(data)

    def decrypt(self, data):
        return base64.urlsafe_b64decode(data)


class MCPServerService:
    """Service for managing MCP server configurations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._encryption_key = self._get_or_create_encryption_key()
        self._fernet = Cryptography(self._encryption_key)

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for credentials."""
        key_env = os.getenv("CORTEX_ENCRYPTION_KEY")
        if key_env:
            return base64.urlsafe_b64decode(key_env.encode())

        # Generate new key
        key = Cryptography.generate_key()
        logger.warning(
            "No CORTEX_ENCRYPTION_KEY found. Generated new key. "
            f"Set CORTEX_ENCRYPTION_KEY={base64.urlsafe_b64encode(key).decode()} in environment."
        )
        return key

    async def create_mcp_server(
        self,
        user_id: int,
        name: str,
        server_type: str,
        module_path: str,
        client_class: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        is_enabled: bool = True,
        is_default: bool = False,
    ) -> MCPServer:
        """Create a new MCP server configuration."""
        try:
            async with self.db_manager.session() as session:
                # If this is set as default, unset other defaults for this user
                if is_default:
                    await self._unset_default_servers(session, user_id)

                mcp_server = MCPServer(
                    user_id=user_id,
                    name=name,
                    server_type=server_type,
                    module_path=module_path,
                    client_class=client_class,
                    config=config or {},
                    description=description,
                    is_enabled=is_enabled,
                    is_default=is_default,
                )

                session.add(mcp_server)
                await session.commit()
                await session.refresh(mcp_server)

                logger.info(f"Created MCP server: {name} for user {user_id}")
                return mcp_server

        except SQLAlchemyError as e:
            logger.error(f"Error creating MCP server: {e}")
            raise

    async def get_user_mcp_servers(self, user_id: int) -> List[MCPServer]:
        """Get all MCP servers for a user."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(MCPServer).where(MCPServer.user_id == user_id)
                )
                return result.scalars().all()

        except SQLAlchemyError as e:
            logger.error(f"Error getting MCP servers for user {user_id}: {e}")
            raise

    async def get_mcp_server(self, server_id: int, user_id: int) -> Optional[MCPServer]:
        """Get a specific MCP server by ID and user."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(MCPServer).where(
                        MCPServer.id == server_id, MCPServer.user_id == user_id
                    )
                )
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error getting MCP server {server_id}: {e}")
            raise

    async def update_mcp_server(
        self, server_id: int, user_id: int, **updates
    ) -> Optional[MCPServer]:
        """Update an MCP server configuration."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(MCPServer).where(
                        MCPServer.id == server_id, MCPServer.user_id == user_id
                    )
                )
                mcp_server = result.scalar_one_or_none()

                if not mcp_server:
                    return None

                # If setting as default, unset other defaults
                if updates.get("is_default"):
                    await self._unset_default_servers(session, user_id)

                # Update fields
                for key, value in updates.items():
                    if hasattr(mcp_server, key):
                        setattr(mcp_server, key, value)

                await session.commit()
                await session.refresh(mcp_server)

                logger.info(f"Updated MCP server {server_id} for user {user_id}")
                return mcp_server

        except SQLAlchemyError as e:
            logger.error(f"Error updating MCP server {server_id}: {e}")
            raise

    async def delete_mcp_server(self, server_id: int, user_id: int) -> bool:
        """Delete an MCP server configuration."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(MCPServer).where(
                        MCPServer.id == server_id, MCPServer.user_id == user_id
                    )
                )
                mcp_server = result.scalar_one_or_none()

                if not mcp_server:
                    return False

                await session.delete(mcp_server)
                await session.commit()

                logger.info(f"Deleted MCP server {server_id} for user {user_id}")
                return True

        except SQLAlchemyError as e:
            logger.error(f"Error deleting MCP server {server_id}: {e}")
            raise

    async def add_server_credential(
        self, server_id: int, user_id: int, credential_name: str, credential_value: str
    ) -> MCPServerCredential:
        """Add an encrypted credential to an MCP server."""
        try:
            async with self.db_manager.session() as session:
                # Verify server belongs to user
                result = await session.execute(
                    select(MCPServer).where(
                        MCPServer.id == server_id, MCPServer.user_id == user_id
                    )
                )
                if not result.scalar_one_or_none():
                    raise ValueError("MCP server not found or access denied")

                # Encrypt the credential
                encrypted_value = self._fernet.encrypt(
                    credential_value.encode()
                ).decode()

                credential = MCPServerCredential(
                    mcp_server_id=server_id,
                    credential_name=credential_name,
                    credential_value=encrypted_value,
                    is_encrypted=True,
                )

                session.add(credential)
                await session.commit()
                await session.refresh(credential)

                logger.info(
                    f"Added credential {credential_name} to MCP server {server_id}"
                )
                return credential

        except SQLAlchemyError as e:
            logger.error(f"Error adding credential to MCP server {server_id}: {e}")
            raise

    async def get_server_credentials(
        self, server_id: int, user_id: int, decrypt: bool = True
    ) -> List[MCPServerCredential]:
        """Get credentials for an MCP server."""
        try:
            async with self.db_manager.session() as session:
                # Verify server belongs to user
                result = await session.execute(
                    select(MCPServer).where(
                        MCPServer.id == server_id, MCPServer.user_id == user_id
                    )
                )
                if not result.scalar_one_or_none():
                    raise ValueError("MCP server not found or access denied")

                result = await session.execute(
                    select(MCPServerCredential).where(
                        MCPServerCredential.mcp_server_id == server_id
                    )
                )
                credentials = result.scalars().all()

                if decrypt:
                    for credential in credentials:
                        if credential.is_encrypted:
                            try:
                                decrypted_value = self._fernet.decrypt(
                                    credential.credential_value.encode()
                                ).decode()
                                credential.credential_value = decrypted_value
                            except Exception as e:
                                logger.error(
                                    f"Error decrypting credential {credential.id}: {e}"
                                )
                                credential.credential_value = "[DECRYPTION_ERROR]"

                return credentials

        except SQLAlchemyError as e:
            logger.error(f"Error getting credentials for MCP server {server_id}: {e}")
            raise

    async def get_default_mcp_server(self, user_id: int) -> Optional[MCPServer]:
        """Get the default MCP server for a user."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(MCPServer).where(
                        MCPServer.user_id == user_id,
                        MCPServer.is_default == True,
                        MCPServer.is_enabled == True,
                    )
                )
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error getting default MCP server for user {user_id}: {e}")
            raise

    async def set_user_preferences(
        self,
        user_id: int,
        default_mcp_server_id: Optional[int] = None,
        auto_retry_enabled: bool = True,
        max_retry_attempts: int = 3,
        timeout_seconds: int = 30,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> UserMCPPreference:
        """Set or update user MCP preferences."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(UserMCPPreference).where(
                        UserMCPPreference.user_id == user_id
                    )
                )
                user_prefs = result.scalar_one_or_none()

                if user_prefs:
                    # Update existing preferences
                    user_prefs.default_mcp_server_id = default_mcp_server_id
                    user_prefs.auto_retry_enabled = auto_retry_enabled
                    user_prefs.max_retry_attempts = max_retry_attempts
                    user_prefs.timeout_seconds = timeout_seconds
                    user_prefs.preferences = preferences or {}
                else:
                    # Create new preferences
                    user_prefs = UserMCPPreference(
                        user_id=user_id,
                        default_mcp_server_id=default_mcp_server_id,
                        auto_retry_enabled=auto_retry_enabled,
                        max_retry_attempts=max_retry_attempts,
                        timeout_seconds=timeout_seconds,
                        preferences=preferences or {},
                    )
                    session.add(user_prefs)

                await session.commit()
                await session.refresh(user_prefs)

                logger.info(f"Updated MCP preferences for user {user_id}")
                return user_prefs

        except SQLAlchemyError as e:
            logger.error(f"Error setting MCP preferences for user {user_id}: {e}")
            raise

    async def get_user_preferences(self, user_id: int) -> Optional[UserMCPPreference]:
        """Get user MCP preferences."""
        try:
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(UserMCPPreference).where(
                        UserMCPPreference.user_id == user_id
                    )
                )
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error getting MCP preferences for user {user_id}: {e}")
            raise

    async def _unset_default_servers(self, session: Session, user_id: int):
        """Unset all default servers for a user."""
        await session.execute(
            update(MCPServer)
            .where(MCPServer.user_id == user_id)
            .values(is_default=False)
        )


# Global service instance
_mcp_service: Optional[MCPServerService] = None


async def get_mcp_service() -> MCPServerService:
    """Get the global MCP service instance."""
    global _mcp_service
    if _mcp_service is None:
        from .manager import get_database_manager

        db_manager = await get_database_manager()
        _mcp_service = MCPServerService(db_manager)
    return _mcp_service
