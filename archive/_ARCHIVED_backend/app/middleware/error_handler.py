import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger('findmynyumba')

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "data": None,
            "error": {"type": "HTTPException", "status_code": exc.status_code},
        },
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = []
    for err in exc.errors():
        field_errors.append({
            "field": " -> ".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed. Check your request data.",
            "data": None,
            "error": {"type": "ValidationError", "details": field_errors},
        },
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f'Unhandled exception | {request.method} {request.url.path} | {str(exc)}', exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An internal server error occurred. Please try again.",
            "data": None,
            "error": {"type": "InternalServerError"},
        },
    )
