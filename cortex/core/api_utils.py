from functools import wraps
from typing import Callable, Any
from fastapi import HTTPException, status
from .logger import get_logger

logger = get_logger(__name__)


def handle_api_errors(
    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    default_message: str = "An error occurred",
):
    """
    Decorator to handle common API errors and convert them to HTTPExceptions.

    Args:
        default_status_code: Default HTTP status code for unhandled exceptions
        default_message: Default error message prefix
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTPExceptions as-is
                raise
            except ValueError as e:
                logger.error(f"Validation error in {func.__name__}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid input: {str(e)}",
                )
            except PermissionError as e:
                logger.error(f"Permission error in {func.__name__}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: {str(e)}",
                )
            except FileNotFoundError as e:
                logger.error(f"Resource not found in {func.__name__}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource not found: {str(e)}",
                )
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                raise HTTPException(
                    status_code=default_status_code,
                    detail=f"{default_message}: {str(e)}",
                )

        return wrapper

    return decorator


def handle_mcp_errors(func: Callable) -> Callable:
    """Specific error handler for MCP-related operations."""
    return handle_api_errors(
        default_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        default_message="MCP operation failed",
    )(func)


def handle_database_errors(func: Callable) -> Callable:
    """Specific error handler for database operations."""
    return handle_api_errors(
        default_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        default_message="Database operation failed",
    )(func)


def handle_auth_errors(func: Callable) -> Callable:
    """Specific error handler for authentication operations."""
    return handle_api_errors(
        default_status_code=status.HTTP_401_UNAUTHORIZED,
        default_message="Authentication failed",
    )(func)
