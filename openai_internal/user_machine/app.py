import asyncio
import inspect
import json
import logging
import os
import time
import traceback
import urllib.parse
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

import traitlets
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from jupyter_client import AsyncKernelClient, AsyncKernelManager, AsyncMultiKernelManager
from pydantic import TypeAdapter

from applied_ace_client.ace_types.user_machine_types import (
    CheckFileResponse,
    CreateKernelRequest,
    CreateKernelResponse,
    GetKernelStateResponse,
    MethodCall,
    MethodCallException,
    MethodCallObjectReferenceReturnValue,
    MethodCallReturnValue,
    ObjectReference,
    RegisterActivityRequest,
    UploadFileRequest,
    UserMachineRequest,
    UserMachineResponseTooLarge,
)

from . import health_check, logger_utils, routes

logger_utils.init_logger_settings()
logger = logging.getLogger(__name__)

if os.getenv("ENVIRONMENT") in ("development", "staging"):
                                                           
                                                                           
    logger.info(f"Setting log level to DEBUG for environment: {os.getenv('ENVIRONMENT')}")
    logger.setLevel(logging.DEBUG)
else:
    logger.info(f"Keeping log level as INFO for environment: {os.getenv('ENVIRONMENT')}")

os.chdir(os.path.expanduser("~"))

_MAX_UPLOAD_SIZE = 1024 * 1024 * 1024
_MAX_DOWNLOAD_TIME = 5 * 60.0
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024       
_MAX_JUPYTER_MESSAGE_SIZE = 10 * 1024 * 1024
_MAX_KERNELS = 20


@asynccontextmanager
async def lifespan(app: FastAPI):
                             
    timeout_task = asyncio.create_task(_kill_old_kernels())
    fill_kernel_queue_task = asyncio.create_task(_fill_kernel_queue())
    health_check_task = asyncio.create_task(HEALTH_CHECK_JOB.run())

    yield

                             
    timeout_task.cancel()
    fill_kernel_queue_task.cancel()
    health_check_task.cancel()


app = FastAPI(lifespan=lifespan)

jupyter_config = traitlets.config.get_config()
                                                                      
                                                                   
                       
                                                                      
                                                             
jupyter_config.KernelRestarter.restart_limit = 0
_MULTI_KERNEL_MANAGER = AsyncMultiKernelManager(config=jupyter_config)

_response_to_callback_from_kernel_futures: dict[str, asyncio.Future] = {}

_timeout_at = {}
_timeout = {}
_kernel_callback_id = {}                                   

_kernel_queue = None
_first_kernel_started = False

HEALTH_CHECK_JOB = health_check.HealthCheckBackgroundJob(
    logger=logger, kernel_manager=_MULTI_KERNEL_MANAGER
)


@dataclass(frozen=True, kw_only=True)
class SelfIdentify:
    value: str

    def to_header(self) -> dict[str, str]:
        return {"x-ace-self-identify": self.value}

    def to_websocket_header(self) -> tuple[bytes, bytes]:
        return b"x-ace-self-identify", self.value.encode("utf-8")

    @classmethod
    def from_env(cls) -> "SelfIdentify":
        self_id = os.getenv("ACE_SELF_IDENTIFY")
        if self_id is None:
            raise ValueError("ACE_SELF_IDENTIFY is not set")
        if not self_id.strip():
            raise ValueError("ACE_SELF_IDENTIFY is empty")

        return cls(value=self_id)


_SELF_IDENTIFY = SelfIdentify.from_env()

_fill_kernel_queue_task_error = None

                                            
_KERNEL_CALLBACK_CONNECTION: dict[str, set[WebSocket]] = {}


class ToolCallbackError(Exception):
                                                                 
    pass


@dataclass
class AsyncKernelClientHolder:
                                                                                                                            
                                                              
     
                                                                                                                    
                                                               
     
                                                                                                     
                                                                                                                                                   
                                                                                 
    value: AsyncKernelClient | None


                                                                                         
async def _kill_old_kernels():
    while True:
        await asyncio.sleep(2.0)
        for kernel_id in list(_timeout_at.keys()):
            if time.monotonic() > _timeout_at[kernel_id]:
                logger.info(
                    f"Killing kernel {kernel_id} due to timeout, {_timeout_at[kernel_id]}, {_timeout[kernel_id]}"
                )
                await _delete_kernel(kernel_id)


async def _fill_kernel_queue():
    global _first_kernel_started, _kernel_queue, _fill_kernel_queue_task_error
    try:
                                                                         
                                                              
        _kernel_queue = asyncio.Queue(maxsize=1)
                                                                                   
                                                                                   
                                         
        kernel_id = None
        kernel_manager = None
        while True:
            logger.info("Create new kernel for pool: Preparing")
            if len(_timeout_at.keys()) >= _MAX_KERNELS:
                logger.info(f"Too many kernels ({_MAX_KERNELS}). Deleting oldest kernel.")
                kernels_to_delete = sorted(
                    _timeout_at.keys(), key=lambda kernel_id: _timeout_at[kernel_id], reverse=True
                )[_MAX_KERNELS - 1 :]
                for kernel_id in kernels_to_delete:
                    logger.info(f"Deleting kernel {kernel_id}")
                    await _delete_kernel(kernel_id)

            logger.info("Create new kernel for pool: Making new kernel")
            start_time = time.monotonic()

            callback_id = str(uuid.uuid4())
            env = os.environ.copy()
            assert "KERNEL_CALLBACK_ID" not in env
            env["KERNEL_CALLBACK_ID"] = callback_id
            kernel_id = None
            try:
                kernel_id = await _MULTI_KERNEL_MANAGER.start_kernel(env=env)
                kernel_manager = _MULTI_KERNEL_MANAGER.get_kernel(kernel_id)
                client = kernel_manager.client()
                client.start_channels()
                await client.wait_for_ready(timeout=30.0)
                client.stop_channels()
                del client
            except Exception as e:
                end_time = time.monotonic()
                logger.exception(
                    f"Create new kernel for pool: Error in {((end_time - start_time) / 1000):.3f} seconds, will shut down the newly started kernel: {kernel_id}"
                )
                if kernel_id is not None:
                    await _MULTI_KERNEL_MANAGER.shutdown_kernel(kernel_id)
                    logger.info(
                        f"Create new kernel for pool: Done shutting down the kernel: {kernel_id}"
                    )
                continue

            end_time = time.monotonic()
            logger.info(
                f"Create new kernel for pool: Done making new kernel in {end_time - start_time:.3f} seconds"
            )
            logger.info(f"Create new kernel for pool: New kernel id {kernel_id}")

            _first_kernel_started = True
                                            
            await _kernel_queue.put((kernel_id, callback_id))
    except Exception as e:
        logger.exception(f"Create new kernel for pool: Unexpected error: {e}")
        _fill_kernel_queue_task_error = traceback.format_exc()
        raise


async def _delete_kernel(kernel_id):
    kernel_ids = _MULTI_KERNEL_MANAGER.list_kernel_ids()
    if kernel_id in kernel_ids:
        kernel_manager = _MULTI_KERNEL_MANAGER.get_kernel(str(kernel_id))
        await kernel_manager.shutdown_kernel()
        _MULTI_KERNEL_MANAGER.remove_kernel(str(kernel_id))
    del _timeout_at[kernel_id]
    del _timeout[kernel_id]
    del _kernel_callback_id[kernel_id]


def _is_from_localhost(request: Request) -> bool:
    if request.client is None:
        return False
    return request.client.host == "127.0.0.1"


async def _forward_callback_from_kernel(call: MethodCall, request: Request):
    if not _is_from_localhost(request):
        raise HTTPException(status_code=403, detail="Forbidden")
    if call.object_reference.type != "callbacks":
        raise HTTPException(
            status_code=400, detail=f"Invalid object reference type {call.object_reference.type}"
        )

    logger.info(f"Forwarding callback request from kernel. {call}")
    _response_to_callback_from_kernel_futures[call.request_id] = asyncio.Future()

    if call.object_reference.id not in _KERNEL_CALLBACK_CONNECTION:
        raise HTTPException(
            status_code=404, detail=f"Unrecognized callback id {call.object_reference.id}"
        )
    conn = _KERNEL_CALLBACK_CONNECTION[call.object_reference.id]
    assert len(conn) != 0
    if len(conn) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"There are multiple websocket connections associated with callback id {call.object_reference.id}",
        )

    await next(iter(conn)).send_text(call.model_dump_json())

    try:
        response = await _response_to_callback_from_kernel_futures[call.request_id]
    except ToolCallbackError as e:
        logger.exception(f"Forwarding callback exception to kernel: {call.request_id}.")
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    finally:
        del _response_to_callback_from_kernel_futures[call.request_id]

    return JSONResponse({"value": response})


app.include_router(routes.get_api_router(_forward_callback_from_kernel), prefix="")


def _respond_to_callback_from_kernel(response: MethodCallReturnValue):
    logger.info("Received callback response.")
    _response_to_callback_from_kernel_futures[response.request_id].set_result(response.value)


def _respond_to_callback_exception_from_kernel(response: MethodCallException):
    logger.info("Received callback exception.")
    _response_to_callback_from_kernel_futures[response.request_id].set_exception(
        ToolCallbackError(response.value)
    )


@app.get("/check_liveness")
async def check_liveness():
    return _check_health()


@app.get("/check_startup")
async def check_startup():
    return _check_health()


def _check_health():
                                                                                   
                                  
     
                                                                              
                                                                       
     
                                                                              
     
                                                                                         
                                                                                           
                                                                                       
                                                                                         

    if not _first_kernel_started:
        logger.info("Reporting health check failure: kernel queue is not initialized")
        return PlainTextResponse(content="Kernel queue is not initialized", status_code=500)

    if _fill_kernel_queue_task_error is not None:
        logger.info(
            "Reporting health check failure: _fill_kernel_queue task failed due to unexpected error"
        )
        return PlainTextResponse(
            content="_fill_kernel_queue task failed due to unexpected error:\n{_fill_kernel_queue_task_error}",
            status_code=500,
        )

    if HEALTH_CHECK_JOB.last_error is not None:
        reason = f"Most recent health_check reported error: {HEALTH_CHECK_JOB.last_error}"
        logger.error(f"Reporting health check failure: {reason}")
        return PlainTextResponse(content=reason, status_code=500)

    if HEALTH_CHECK_JOB.is_stale():
        reason = "Most recent successful health check is too old"
        if HEALTH_CHECK_JOB.last_success_at is not None:
            reason = f"Most recent successful health check is {time.monotonic() - HEALTH_CHECK_JOB.last_success_at} seconds old"
                                                               
            logger.error(f"Reporting health check failure: {reason}")
        return PlainTextResponse(content=reason, status_code=500)

    return PlainTextResponse(content="success")


@app.get("/self_identify")
async def self_identify():
    return PlainTextResponse("")


@app.post("/upload")
async def upload(upload_request: str = Form(), file: UploadFile = File()):
    logger.info("Upload request")
    request = TypeAdapter(UploadFileRequest).validate_python(json.loads(upload_request))
    try:
        total_size = 0
        with open(request.destination, "wb") as f:
            while chunk := file.file.read():
                total_size += len(chunk)
                if total_size > _MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large",
                    )
                f.write(chunk)
    except Exception:
        try:
            os.remove(request.destination)
        except Exception as e:
            logger.exception(f"Error while removing file: {request.destination}", exc_info=e)
        raise

    logger.info(f"Upload request complete. {upload_request}")
    return JSONResponse(content={})


@app.get("/download/{path:path}")
async def download(path: str):
    path = urllib.parse.unquote(path)
    if not os.path.isfile(path):
        raise HTTPException(404, f"File not found: {path}")

    logger.info(f"Download request. {path}")

    def iterfile():
        with open(path, "rb") as f:
            while chunk := f.read(_DOWNLOAD_CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iterfile(),
        headers={"Content-Length": f"{os.path.getsize(path)}"},
        media_type="application/octet-stream",
    )


@app.get("/check_file/{path:path}")
async def check_file(path: str):
    path = "/" + urllib.parse.unquote(path)
    logger.info(f"Check file request. {path}")
    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    return CheckFileResponse(exists=exists, size=size, too_large=False)


@app.get("/kernel/{kernel_id}")
async def kernel_state(kernel_id: str):
    logger.info(f"Get kernel state request. {kernel_id}")
    if kernel_id not in _timeout_at:
        time_remaining_ms = 0.0
    else:
        time_remaining_ms = max(0.0, _timeout_at[kernel_id] - time.monotonic()) * 1000.0

    return GetKernelStateResponse(time_remaining_ms=time_remaining_ms)


@app.delete("/kernel/{kernel_id}")
async def delete_kernel(kernel_id: str):
    logger.info(f"Delete kernel request. {kernel_id}")
    if kernel_id not in _timeout_at:
        return JSONResponse(status_code=404, content={"error": f"Kernel {kernel_id} not found."})

    await _delete_kernel(kernel_id)
    return JSONResponse(content={})


@app.post("/kernel")
async def create_kernel(create_kernel_request: CreateKernelRequest):
    logger.info(f"Create kernel request. {create_kernel_request}")
    kernel_idle_timeout = create_kernel_request.timeout
    try:
                                                                                          
                                                                              
        kernel_id, callback_id = await asyncio.wait_for(_kernel_queue.get(), timeout=60.0)
    except TimeoutError:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Timeout trying to create a kernel"
        )
    _timeout[kernel_id] = kernel_idle_timeout
    _timeout_at[kernel_id] = time.monotonic() + kernel_idle_timeout
    _kernel_callback_id[kernel_id] = callback_id
    logger.info(f"Got kernel id from queue. {create_kernel_request}")
    return CreateKernelResponse(kernel_id=kernel_id)


                                                                        
@app.websocket("/channel")
async def channel(websocket: WebSocket):
    await websocket.accept(headers=[_SELF_IDENTIFY.to_websocket_header()])

    clients: dict[str, AsyncKernelClientHolder] = {}
    registered_callback_ids = set()
                                      
                                                               
                                                                             
                                                           
                                                                                
                                         
     
                                                                  
    recv_from_api_server = asyncio.create_task(websocket.receive_text())
    recv_from_jupyter = None
    try:
        while True:
            logger.debug(f"Waiting for message. {recv_from_api_server}, {recv_from_jupyter}")
            done, _ = await asyncio.wait(
                [task for task in [recv_from_api_server, recv_from_jupyter] if task is not None],
                return_when=asyncio.FIRST_COMPLETED,
            )
            logger.debug(f"Got messages for {done}.")
            if recv_from_api_server in done:
                done_future = recv_from_api_server
                recv_from_api_server = asyncio.create_task(websocket.receive_text())
                request = TypeAdapter(UserMachineRequest).validate_python(
                    json.loads(done_future.result())
                )
                logger.debug(f"Received message from API server. {request}")
                if isinstance(request, RegisterActivityRequest):
                    logger.debug(f"Registering activity. {request}")
                    _timeout_at[request.kernel_id] = time.monotonic() + _timeout[request.kernel_id]
                elif isinstance(request, MethodCallReturnValue):
                    _respond_to_callback_from_kernel(request)
                elif isinstance(request, MethodCallException):
                    _respond_to_callback_exception_from_kernel(request)
                elif isinstance(request, MethodCall):

                    async def run(request: UserMachineRequest):
                        try:
                            object_reference = request.object_reference
                            if object_reference.type == "multi_kernel_manager":
                                referenced_object = _MULTI_KERNEL_MANAGER
                            elif object_reference.type == "kernel_manager":
                                referenced_object = _MULTI_KERNEL_MANAGER.get_kernel(
                                    object_reference.id
                                )
                                callback_id = _kernel_callback_id[object_reference.id]
                                                                       
                                logger.debug("Setting callback forward function.")
                                registered_callback_ids.add(callback_id)
                                if callback_id not in _KERNEL_CALLBACK_CONNECTION:
                                    _KERNEL_CALLBACK_CONNECTION[callback_id] = {websocket}
                                else:
                                    _KERNEL_CALLBACK_CONNECTION[callback_id].add(websocket)

                            elif object_reference.type == "client":
                                referenced_object = clients[object_reference.id]
                            else:
                                raise Exception(
                                    f"Unknown object reference type: {object_reference.type}"
                                )
                            qualified_method = f"{object_reference.type}.{request.method}"
                            logger.debug(
                                f"Method call: {qualified_method} args: {request.args} kwargs: {request.kwargs}"
                            )

                            if isinstance(referenced_object, AsyncKernelClientHolder):
                                value = getattr(referenced_object.value, request.method)(
                                    *request.args, **request.kwargs
                                )
                            else:
                                value = getattr(referenced_object, request.method)(
                                    *request.args, **request.kwargs
                                )

                            if inspect.isawaitable(value):
                                value = await value
                            if isinstance(value, AsyncKernelClient):
                                value = AsyncKernelClientHolder(value)
                            return (request.request_id, value, None)
                        except Exception as e:
                            return (request.request_id, None, e)

                    assert recv_from_jupyter is None
                    recv_from_jupyter = asyncio.create_task(run(request))
            if recv_from_jupyter in done:
                done_future = recv_from_jupyter
                recv_from_jupyter = None
                request_id, value, e = done_future.result()
                if e is None:
                    logger.debug(f"Received result from Jupyter. {value}")
                    if isinstance(value, AsyncKernelClientHolder):
                        client_id = str(uuid.uuid4())
                        clients[client_id] = value
                        result = MethodCallObjectReferenceReturnValue(
                            request_id=request_id,
                            object_reference=ObjectReference(type="client", id=client_id),
                        )
                    elif isinstance(value, AsyncKernelManager):
                        result = MethodCallObjectReferenceReturnValue(
                            request_id=request_id,
                            object_reference=ObjectReference(
                                type="kernel_manager", id=value.kernel_id
                            ),
                        )
                    else:
                        result = MethodCallReturnValue(request_id=request_id, value=value)
                else:
                    logger.debug(f"Received result from Jupyter. Exception: {value}")
                    result = MethodCallException(
                        request_id=request_id,
                        type=type(e).__name__,
                        value=str(e),
                        traceback=traceback.format_tb(e.__traceback__),
                    )
                                                                                         
                    del e

                                           
                message = result.model_dump_json()
                logger.debug(f"Sending response: {type(result)}, {len(message)}")
                if len(message) > _MAX_JUPYTER_MESSAGE_SIZE:
                    logger.error(f"Response too large: {len(message)}")
                    e = UserMachineResponseTooLarge(
                        f"Message of type {type(result)} is too large: {len(message)}"
                    )
                    message = MethodCallException(
                        request_id=result.request_id,
                        type=type(e).__name__,
                        value=str(e),
                        traceback=traceback.format_tb(e.__traceback__),
                    ).model_dump_json()

                await websocket.send_text(message)
                logger.debug("Response sent.")
    except WebSocketDisconnect as e:
        if e.code == 1000:
            logger.debug("Client WebSocket connection closed normally")
        else:
            logger.exception(f"Client WebSocket connection closed with code {e.code}")
    finally:
        try:
            for client in clients.values():
                if client.value is not None:
                    client.value.stop_channels()
                    client.value = None
            logger.debug("All client channels stopped.")
        except Exception:
            logger.exception("Error while stopping client channels.")

        for callback_id in registered_callback_ids:
            conn = _KERNEL_CALLBACK_CONNECTION.get(callback_id)
            if conn is None:
                logger.error(f"Callback {callback_id} not found")
            else:
                conn.remove(websocket)
                if len(conn) == 0:
                    del _KERNEL_CALLBACK_CONNECTION[callback_id]


@app.middleware("http")
async def add_self_identify_header(request: Request, call_next):
                                                                                                  
    if _is_from_localhost(request):
                                                                                                  
        return await call_next(request)
    try:
        response = await call_next(request)
    except Exception:
                                                                                     
                                                                                      
                                                                                 
                                    
        traceback.print_exc()
        return PlainTextResponse(
            "Internal server error",
            status_code=500,
            headers=_SELF_IDENTIFY.to_header(),
        )
    for header, value in _SELF_IDENTIFY.to_header().items():
        response.headers[header] = value
    return response
