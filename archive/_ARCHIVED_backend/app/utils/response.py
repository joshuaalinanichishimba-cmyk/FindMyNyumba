from fastapi.responses import JSONResponse
from typing import Any, Optional

def api_response(
    success: bool,
    message: str,
    data: Any = None,
    error: Any = None,
    status_code: int = 200,
) -> JSONResponse:
    """The ONLY function used to build every API response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "message": message,
            "data":    data,
            "error":   error,
        },
    )

def success_response(
    message: str,
    data: Any = None,
    status_code: int = 200,
) -> JSONResponse:
    return api_response(
        success=True,
        message=message,
        data=data,
        error=None,
        status_code=status_code,
    )

def error_response(
    message: str,
    error: Any = None,
    status_code: int = 400,
) -> JSONResponse:
    return api_response(
        success=False,
        message=message,
        data=None,
        error=error,
        status_code=status_code,
    )

def created_response(message: str, data: Any = None) -> JSONResponse:
    return success_response(message, data=data, status_code=201)
