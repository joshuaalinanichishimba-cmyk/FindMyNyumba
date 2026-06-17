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

    def _clean_errors(exc):
        """Pydantic v2 puts raw ValueError objects in ctx, which aren't JSON
        serializable. Return the first readable message plus a safe list."""
        out = []
        for e in exc.errors():
            msg = e.get("msg", "Invalid value")
            field = e.get("loc", ["body"])[-1]
            out.append({"field": str(field), "message": str(msg)})
        return out

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errs = _clean_errors(exc)
        return JSONResponse(
            status_code=422,
            content={"success": False, "detail": errs[0]["message"] if errs else "Invalid input", "errors": errs},
        )

    @app.exception_handler(CoreValidationError)
    async def pydantic_validation_handler(request: Request, exc: CoreValidationError):
        errs = _clean_errors(exc)
        return JSONResponse(
            status_code=422,
            content={"success": False, "detail": errs[0]["message"] if errs else "Invalid input", "errors": errs},
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