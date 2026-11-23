import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.server.models.enums import ErrorCode
from src.server.simulation.exceptions import located
from src.server.utils.logger import alert_logger, sim_logger


# The code tells the UI what happened; the status only says whose fault it is.
STATUS_BY_CODE = {
    ErrorCode.INVALID_COMBO: 400,
    ErrorCode.INVALID_DATA: 500,
    ErrorCode.NOT_ENTERED: 501,
    ErrorCode.NOT_SUPPORTED: 501,
    ErrorCode.INTERNAL: 500,
}


def new_error_id() -> str:
    return uuid.uuid4().hex[:8]


def error_response(code: ErrorCode, detail: str, error_id: str) -> JSONResponse:
    return JSONResponse(status_code=STATUS_BY_CODE[code], content={"detail": detail, "code": code.value, "error_id": error_id})


def simulation_failed(request: BaseModel, error: Exception) -> JSONResponse:
    """Logs the whole request with the traceback, so every failed simulation can be replayed as a test."""
    error = located(error)
    error_id = new_error_id()
    sim_logger.error(f"[{error_id}] [{error.code.value}] {error}\nRequest: {request.json()}", exc_info=error)
    return error_response(error.code, str(error), error_id)


async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
    error_id = new_error_id()
    alert_logger.error(f"[{error_id}] {request.method} {request.url.path}: {type(error).__name__}: {error}", exc_info=error)
    return error_response(ErrorCode.INTERNAL, f"{type(error).__name__}: {error}", error_id)


def add_error_handlers(app: FastAPI) -> None:
    # Starlette still re-raises after this handler, so uvicorn prints the traceback to the console as before.
    app.add_exception_handler(Exception, unexpected_error)
