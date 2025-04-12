from typing import Any, Literal

import pydantic


class ObjectReference(pydantic.BaseModel):
    type: Literal[
        "multi_kernel_manager",
        "kernel_manager",
        "client",
        "callbacks",
    ]
    id: str


class MethodCall(pydantic.BaseModel):                          
    message_type: Literal["call_request"] = "call_request"
    object_reference: ObjectReference
    request_id: str
    method: str
    args: list[Any]
                                                                                          
    kwargs: dict[str, Any]


class MethodCallException(pydantic.BaseModel):
    message_type: Literal["call_exception"] = "call_exception"
    request_id: str
    type: str
    value: str
    traceback: list[str]


class MethodCallReturnValue(pydantic.BaseModel):
    message_type: Literal["call_return_value"] = "call_return_value"
    request_id: str
    value: Any = None


class MethodCallObjectReferenceReturnValue(pydantic.BaseModel):
    message_type: Literal["call_object_reference"] = "call_object_reference"
    request_id: str
    object_reference: ObjectReference


class UploadFileRequest(pydantic.BaseModel):
    message_type: Literal["upload_file_request"] = "upload_file_request"
    destination: str


class UploadFileFromUrlRequest(pydantic.BaseModel):
    message_type: Literal["upload_file_from_url_request"] = "upload_file_from_url_request"
    source_url: str
    destination: str


class DownloadFileToUrlRequest(pydantic.BaseModel):
    message_type: Literal["download_file_to_url_request"] = "download_file_to_url_request"
    source: str
    destination_url: str


class CheckFileResponse(pydantic.BaseModel):
    message_type: Literal["check_file_response"] = "check_file_response"
                                                                           
                             
    exists: bool
    too_large: bool
    size: int
    user_machine_exists: bool = True


class CreateKernelRequest(pydantic.BaseModel):
    message_type: Literal["create_kernel_request"] = "create_kernel_request"
    timeout: float
    language: str


class CreateKernelResponse(pydantic.BaseModel):
    message_type: Literal["create_kernel_response"] = "create_kernel_response"
    kernel_id: str


class GetKernelStateResponse(pydantic.BaseModel):
    message_type: Literal["get_kernel_state_response"] = "get_kernel_state_response"
    time_remaining_ms: float


class RegisterActivityRequest(pydantic.BaseModel):
    message_type: Literal["register_activity_request"] = "register_activity_request"
    kernel_id: str


UserMachineRequest = (
    MethodCall
    | MethodCallException
    | MethodCallReturnValue
    | MethodCallObjectReferenceReturnValue
    | RegisterActivityRequest
)


UserMachineResponse = (
    MethodCall | MethodCallException | MethodCallReturnValue | MethodCallObjectReferenceReturnValue
)


class AceException(Exception):
    pass


class UserMachineResponseTooLarge(AceException):
    pass


def parse_raw_as_user_machine_request(s: str | bytes) -> UserMachineRequest:
    return pydantic.TypeAdapter(UserMachineRequest).validate_json(s)                


def parse_raw_as_user_machine_response(s: str | bytes) -> UserMachineResponse:
    return pydantic.TypeAdapter(UserMachineResponse).validate_json(s)                
