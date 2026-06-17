from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic_core import ValidationError as CoreValidationError


def setup_exception_handlers(app: FastAPI):

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"success": False, "detail": exc.errors()},
        )

    @app.exception_handler(CoreValidationError)
    async def pydantic_validation_handler(request: Request, exc: CoreValidationError):
        return JSONResponse(
            status_code=422,
            content={"success": False, "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Real error is logged server-side (Sentry/Render logs); client sees generic text.
        import logging
        logging.getLogger("findmynyumba").exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": "Something went wrong."},
        )