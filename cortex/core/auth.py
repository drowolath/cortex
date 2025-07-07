import hashlib
import secrets
import bcrypt
import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .logger import get_logger
from .database import User as UserModel, Token as TokenModel

logger = get_logger("auth")


class AuthError(Exception):
    """Base exception for authentication errors."""

    pass


class InvalidCredentialsError(AuthError):
    """Raised when credentials are invalid."""

    pass


class TokenExpiredError(AuthError):
    """Raised when token has expired."""

    pass


class UserNotFoundError(AuthError):
    """Raised when user is not found."""

    pass


class UserExistsError(AuthError):
    """Raised when trying to create a user that already exists."""

    pass


@dataclass
class AuthUser:
    """Framework-agnostic user representation."""

    username: str
    is_active: bool = True
    user_id: Optional[int] = None


@dataclass
class AuthToken:
    """Framework-agnostic token representation."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    expires_at: Optional[datetime] = None


class TokenManager:
    """Manages JWT token operations."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        expires_minutes: int = 60,
    ):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.algorithm = algorithm
        self.expires_minutes = expires_minutes

    def create_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.expires_minutes
            )

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.PyJWTError as exc:
            logger.error(f"Token decoding error: {exc}")
            return None

    def hash_token(self, token: str) -> str:
        """Hash token for database storage."""
        return hashlib.sha256(token.encode()).hexdigest()


class PasswordManager:
    """Manages password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password using bcrypt."""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )


class UserService:
    """Service for user management operations."""

    def __init__(self, password_manager: PasswordManager):
        self.password_manager = password_manager

    async def create_user(
        self, db: AsyncSession, username: str, password: str, is_active: bool = True
    ) -> AuthUser:
        """Create a new user."""
        # Check if user already exists
        result = await db.execute(
            select(UserModel).where(UserModel.username == username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise UserExistsError(f"User '{username}' already exists")

        # Create new user
        password_hash = self.password_manager.hash_password(password)
        user_model = UserModel(
            username=username, password_hash=password_hash, is_active=is_active
        )

        db.add(user_model)
        await db.commit()
        await db.refresh(user_model)

        logger.info(f"User '{username}' created successfully")
        return AuthUser(
            username=user_model.username,
            is_active=user_model.is_active,
            user_id=user_model.id,
        )

    async def get_user(self, db: AsyncSession, username: str) -> Optional[AuthUser]:
        """Get user by username."""
        result = await db.execute(
            select(UserModel).where(UserModel.username == username)
        )
        user_model = result.scalar_one_or_none()

        if not user_model:
            return None

        return AuthUser(
            username=user_model.username,
            is_active=user_model.is_active,
            user_id=user_model.id,
        )

    async def authenticate_user(
        self, db: AsyncSession, username: str, password: str
    ) -> Optional[AuthUser]:
        """Authenticate user credentials."""
        result = await db.execute(
            select(UserModel).where(
                and_(UserModel.username == username, UserModel.is_active == True)
            )
        )
        user_model = result.scalar_one_or_none()

        if not user_model:
            return None

        if not self.password_manager.verify_password(
            password, user_model.password_hash
        ):
            return None

        return AuthUser(
            username=user_model.username,
            is_active=user_model.is_active,
            user_id=user_model.id,
        )

    async def update_user_status(
        self, db: AsyncSession, username: str, is_active: bool
    ) -> bool:
        """Update user active status."""
        result = await db.execute(
            update(UserModel)
            .where(UserModel.username == username)
            .values(is_active=is_active)
        )

        if result.rowcount > 0:
            await db.commit()
            logger.info(f"User '{username}' status updated to active={is_active}")
            return True

        return False


class TokenService:
    """Service for token management operations."""

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager

    async def create_and_store_token(
        self, db: AsyncSession, username: str, expires_delta: Optional[timedelta] = None
    ) -> AuthToken:
        """Create token and store in database."""
        # Create JWT token
        token = self.token_manager.create_token(
            data={"sub": username}, expires_delta=expires_delta
        )

        # Calculate expiration
        if expires_delta:
            expires_at = datetime.now(timezone.utc) + expires_delta
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=self.token_manager.expires_minutes
            )

        # Store token in database
        token_hash = self.token_manager.hash_token(token)
        token_model = TokenModel(
            token_hash=token_hash,
            username=username,
            expires_at=expires_at,
            is_revoked=False,
        )

        db.add(token_model)
        await db.commit()

        logger.info(f"Token created and stored for user: {username}")

        return AuthToken(
            access_token=token,
            token_type="bearer",
            expires_in=self.token_manager.expires_minutes * 60,
            expires_at=expires_at,
        )

    async def verify_token(
        self, db: AsyncSession, token: str
    ) -> Optional[Dict[str, Any]]:
        """Verify token and check if it's active in database."""
        # Decode JWT token
        payload = self.token_manager.decode_token(token)
        if not payload:
            return None

        username = payload.get("sub")
        if not username:
            return None

        # Check if token exists in database and is not revoked
        token_hash = self.token_manager.hash_token(token)
        result = await db.execute(
            select(TokenModel).where(
                and_(
                    TokenModel.token_hash == token_hash,
                    TokenModel.is_revoked == False,
                    TokenModel.expires_at > datetime.now(timezone.utc),
                )
            )
        )
        token_model = result.scalar_one_or_none()

        if not token_model:
            return None

        return {"username": username, "token": token}

    async def revoke_token(self, db: AsyncSession, token: str) -> bool:
        """Revoke a token."""
        token_hash = self.token_manager.hash_token(token)

        result = await db.execute(
            update(TokenModel)
            .where(TokenModel.token_hash == token_hash)
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )

        if result.rowcount > 0:
            await db.commit()
            logger.info("Token revoked successfully")
            return True

        return False

    async def cleanup_expired_tokens(self, db: AsyncSession) -> int:
        """Remove expired tokens from database."""
        result = await db.execute(
            select(TokenModel).where(TokenModel.expires_at < datetime.now(timezone.utc))
        )
        expired_tokens = result.scalars().all()

        for token in expired_tokens:
            await db.delete(token)

        count = len(expired_tokens)
        if count > 0:
            await db.commit()
            logger.info(f"Cleaned up {count} expired tokens")

        return count

    async def revoke_user_tokens(self, db: AsyncSession, username: str) -> int:
        """Revoke all tokens for a user."""
        result = await db.execute(
            update(TokenModel)
            .where(
                and_(TokenModel.username == username, TokenModel.is_revoked == False)
            )
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )

        count = result.rowcount
        if count > 0:
            await db.commit()
            logger.info(f"Revoked {count} tokens for user: {username}")

        return count


class AuthenticationService:
    """Main authentication service that coordinates all auth operations."""

    def __init__(
        self, secret_key: Optional[str] = None, token_expires_minutes: int = 60
    ):
        self.password_manager = PasswordManager()
        self.token_manager = TokenManager(
            secret_key=secret_key, expires_minutes=token_expires_minutes
        )
        self.user_service = UserService(self.password_manager)
        self.token_service = TokenService(self.token_manager)

    async def login(self, db: AsyncSession, username: str, password: str) -> AuthToken:
        """Authenticate user and create token."""
        user = await self.user_service.authenticate_user(db, username, password)
        if not user:
            raise InvalidCredentialsError("Invalid username or password")

        if not user.is_active:
            raise InvalidCredentialsError("User account is disabled")

        token = await self.token_service.create_and_store_token(db, username)
        logger.info(f"User '{username}' logged in successfully")
        return token

    async def logout(self, db: AsyncSession, token: str) -> bool:
        """Logout user by revoking token."""
        success = await self.token_service.revoke_token(db, token)
        if success:
            logger.info("User logged out successfully")
        return success

    async def get_current_user(self, db: AsyncSession, token: str) -> AuthUser:
        """Get current user from token."""
        token_data = await self.token_service.verify_token(db, token)

        if not token_data:
            raise InvalidCredentialsError("Could not validate credentials")

        user = await self.user_service.get_user(db, token_data["username"])
        if not user:
            raise UserNotFoundError("User not found")

        if not user.is_active:
            raise InvalidCredentialsError("User account is disabled")

        return user

    async def create_user(
        self, db: AsyncSession, username: str, password: str, is_active: bool = True
    ) -> AuthUser:
        """Create a new user."""
        return await self.user_service.create_user(db, username, password, is_active)

    async def change_password(
        self, db: AsyncSession, username: str, old_password: str, new_password: str
    ) -> bool:
        """Change user password."""
        # Verify old password
        user = await self.user_service.authenticate_user(db, username, old_password)
        if not user:
            raise InvalidCredentialsError("Current password is incorrect")

        # Update password
        new_hash = self.password_manager.hash_password(new_password)
        result = await db.execute(
            update(UserModel)
            .where(UserModel.username == username)
            .values(password_hash=new_hash)
        )

        if result.rowcount > 0:
            await db.commit()
            # Revoke all existing tokens for security
            await self.token_service.revoke_user_tokens(db, username)
            logger.info(f"Password changed for user: {username}")
            return True

        return False

    async def cleanup_expired_tokens(self, db: AsyncSession) -> int:
        """Cleanup expired tokens."""
        return await self.token_service.cleanup_expired_tokens(db)


auth_service = AuthenticationService(secret_key=os.getenv("JWT_SECRET_KEY"))


def get_auth_service() -> AuthenticationService:
    """Get the global authentication service instance."""
    return auth_service
