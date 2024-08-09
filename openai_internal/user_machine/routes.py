import logging
from typing import Any, Callable, Coroutine

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from applied_ace_client.ace_types.user_machine_types import MethodCall

logger = logging.getLogger(__name__)


class SerializedException(BaseModel):
    id: str
    type: str
    value: str
    traceback: str


class LogExceptionRequest(BaseModel):
    message: str
    exception: SerializedException
    orig_func_name: str | None = None
    orig_func_args: str | None = None
    orig_func_kwargs: str | None = None


class LogMatplotlibFallbackRequest(BaseModel):
    reason: str
    metadata: dict[str, Any] | None = None


def get_api_router(
    send_callback: Callable[[MethodCall, Request], Coroutine[Any, Any, JSONResponse]]
):
    api_router = APIRouter()

    @api_router.post("/ace_tools/call_function")
    async def call_function(call: MethodCall, request: Request):
        logger.info(f"Calling function {call.method}", extra={"callback_function": call.method})

        return await send_callback(call, request)

    @api_router.post("/ace_tools/log_exception")
    async def log_exception(body: LogExceptionRequest, request: Request):
        logger.error(
            f"ace_tools exception logger: {body.message}, id={body.exception.id}, orig_func_name={body.orig_func_name}, type={body.exception.type}, value={body.exception.value}",
            extra={
                "custom_message": body.message,
                "exception_id": body.exception.id,
                "exception_type": body.exception.type,
                "exception": body.exception.value,
                "traceback": body.exception.traceback,
                "orig_func_name": body.orig_func_name,
                "orig_func_args": body.orig_func_args,
                "orig_func_kwargs": body.orig_func_kwargs,
            },
        )
                                         

    @api_router.post("/ace_tools/log_matplotlib_img_fallback")
    async def log_matplotlib_img_fallback(body: LogMatplotlibFallbackRequest, request: Request):
        logger.warning(
            f"ace_tools matplotlib img fallback: reason={body.reason} metadata={body.metadata}",
            extra={
                "reason": body.reason,
                "metadata": body.metadata,
            },
        )

    return api_router
