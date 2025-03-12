from typing import Any, Literal, cast

import pydantic


class JupyterStartMessage(pydantic.BaseModel):
    msg_type: Literal["@start_message"] = "@start_message"
    run_id: str
    code: str
    code_message_id: str
    start_time: float


class JupyterTimeoutMessage(pydantic.BaseModel):
    msg_type: Literal["@timeout"] = "@timeout"
    timeout: float


                                                                
                                                                                                      


class IOPubParentHeader(pydantic.BaseModel):
    msg_id: str
    version: str


class IOPubStatusContent(pydantic.BaseModel):
    execution_state: Literal["busy", "idle", "starting"]


class IOPubStatus(pydantic.BaseModel):
    msg_type: Literal["status"]
    parent_header: IOPubParentHeader
    content: IOPubStatusContent


class IOPubStreamContent(pydantic.BaseModel):
    name: Literal["stdout", "stderr"]
    text: str


class IOPubStream(pydantic.BaseModel):
    msg_type: Literal["stream"]
    parent_header: IOPubParentHeader
    content: IOPubStreamContent


IOPubMimeBundle = dict[str, str]


class IOPubExecuteResultContent(pydantic.BaseModel):
    data: IOPubMimeBundle


class IOPubExecuteResult(pydantic.BaseModel):
    msg_type: Literal["execute_result"]
    parent_header: IOPubParentHeader
    content: IOPubExecuteResultContent


class IOPubDisplayDataContent(pydantic.BaseModel):
    data: IOPubMimeBundle


class IOPubDisplayData(pydantic.BaseModel):
    msg_type: Literal["display_data"]
    parent_header: IOPubParentHeader
    content: IOPubDisplayDataContent


class IOPubErrorContent(pydantic.BaseModel):
    traceback: list[str]
    ename: str
    evalue: str


class IOPubError(pydantic.BaseModel):
    msg_type: Literal["error"]
    parent_header: IOPubParentHeader
    content: IOPubErrorContent


class IOPubExecuteInput(pydantic.BaseModel):
    msg_type: Literal["execute_input"]
    parent_header: IOPubParentHeader


IOPubMessage = (
    IOPubStatus
    | IOPubStream
    | IOPubExecuteResult
    | IOPubDisplayData
    | IOPubError
    | IOPubExecuteInput
)


def parse_io_pub_message(message_json: dict[str, Any]) -> IOPubMessage:
    model: type[pydantic.BaseModel]

    match message_json["msg_type"]:
        case "status":
            model = IOPubStatus
        case "stream":
            model = IOPubStream
        case "execute_result":
            model = IOPubExecuteResult
        case "display_data":
            model = IOPubDisplayData
        case "error":
            model = IOPubError
        case "execute_input":
            model = IOPubExecuteInput
        case _:
            raise ValueError(f"Unknown message type: {message_json['msg_type']}")

    return cast(IOPubMessage, pydantic.TypeAdapter(model).validate_python(message_json))


JupyterMessage = JupyterStartMessage | JupyterTimeoutMessage | IOPubMessage
