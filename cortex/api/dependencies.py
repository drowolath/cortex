from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.auth import (
    get_auth_service,
    InvalidCredentialsError,
    UserNotFoundError,
    AuthUser,
)
from ..core.database import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    auth_service=Depends(get_auth_service),
) -> AuthUser:
    """FastAPI dependency to get current authenticated user."""
    try:
        token = credentials.credentials
        user = await auth_service.get_current_user(db, token)
        return user
    except (InvalidCredentialsError, UserNotFoundError) as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
