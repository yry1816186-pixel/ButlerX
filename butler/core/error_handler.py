from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union
from functools import wraps
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ButlerError(Exception):
    """Base exception for Butler application."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "BUTLER_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(ButlerError):
    """Authentication related errors."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=401,
            details=details,
        )


class AuthorizationError(ButlerError):
    """Authorization related errors."""
    
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )


class ValidationError(ButlerError):
    """Input validation errors."""
    
    def __init__(self, message: str = "Invalid input", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class ResourceNotFoundError(ButlerError):
    """Resource not found errors."""
    
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class RateLimitError(ButlerError):
    """Rate limit errors."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            status_code=429,
            details=details,
        )


class ServiceUnavailableError(ButlerError):
    """Service unavailable errors."""
    
    def __init__(self, message: str = "Service unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=details,
        )


def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR,
) -> None:
    """Log an error with context information.
    
    Args:
        error: The exception to log
        context: Additional context information
        level: Logging level
    """
    context = context or {}
    
    if isinstance(error, ButlerError):
        log_data = {
            "error_code": error.error_code,
            "message": error.message,
            "status_code": error.status_code,
            "details": error.details,
            **context,
        }
        logger.log(level, "ButlerError: %s", log_data)
    else:
        log_data = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            **context,
        }
        logger.log(level, "Exception: %s", log_data)


def handle_error(
    error: Exception,
    request: Optional[Request] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Handle an error and return status code and response data.
    
    Args:
        error: The exception to handle
        request: Optional request context
        
    Returns:
        Tuple of (status_code, response_dict)
    """
    request_id = getattr(request.state, "request_id", "unknown") if request else "unknown"
    
    if isinstance(error, ButlerError):
        log_error(error, {"request_id": request_id})
        return (
            error.status_code,
            {
                "status": "error",
                "error": error.error_code,
                "message": error.message,
                "request_id": request_id,
                **error.details,
            },
        )
    elif isinstance(error, HTTPException):
        log_error(
            Exception(f"HTTP {error.status_code}: {error.detail}"),
            {"request_id": request_id},
        )
        return (
            error.status_code,
            {
                "status": "error",
                "error": "HTTP_ERROR",
                "message": error.detail,
                "request_id": request_id,
            },
        )
    else:
        log_error(error, {"request_id": request_id})
        return (
            500,
            {
                "status": "error",
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "request_id": request_id,
            },
        )


def safe_execute(
    error_message: str = "Operation failed",
    error_code: str = "EXECUTION_ERROR",
    status_code: int = 500,
    default_return: Any = None,
):
    """Decorator for safe execution of functions with error handling.
    
    Args:
        error_message: Default error message
        error_code: Default error code
        status_code: Default HTTP status code
        default_return: Value to return on error
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ButlerError:
                raise
            except Exception as e:
                log_error(e, {"function": func.__name__})
                raise ButlerError(
                    message=error_message,
                    error_code=error_code,
                    status_code=status_code,
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ButlerError:
                raise
            except Exception as e:
                log_error(e, {"function": func.__name__})
                raise ButlerError(
                    message=error_message,
                    error_code=error_code,
                    status_code=status_code,
                )
        
        if hasattr(func, "__await__"):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def create_error_response(status_code: int, error_data: Dict[str, Any]) -> JSONResponse:
    """Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        error_data: Error data dictionary
        
    Returns:
        JSONResponse with error information
    """
    return JSONResponse(
        status_code=status_code,
        content=error_data,
    )


async def butler_exception_handler(request: Request, call_next):
    """Global exception handler for FastAPI.
    
    Args:
        request: Incoming request
        call_next: Next middleware or route handler
        
    Returns:
        Response or calls next handler
    """
    try:
        return await call_next(request)
    except ButlerError as e:
        status_code, error_data = handle_error(e, request)
        return create_error_response(status_code, error_data)
    except HTTPException as e:
        status_code, error_data = handle_error(e, request)
        return create_error_response(status_code, error_data)
    except Exception as e:
        status_code, error_data = handle_error(e, request)
        return create_error_response(status_code, error_data)
