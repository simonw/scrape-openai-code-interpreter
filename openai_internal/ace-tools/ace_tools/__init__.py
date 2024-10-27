import os
import re
import sys
import traceback
import uuid
from typing import Any

import pandas as pd
import requests

sys.path.append("/home/sandbox/.openai_internal/")
from applied_ace_client.ace_types.user_machine_types import MethodCall, ObjectReference

_BASE_URL = "http://localhost"
_USER_MACHINE_PORT = 8080


def _call_function(
    function_name: str, function_args: list[Any], function_kwargs: dict[str, Any]
) -> Any:
                                                                        
     
            
                                   
     
                                                                                      
                          
                                                                        
     
                                                                  
    response = requests.post(
        f"{_BASE_URL}:{_USER_MACHINE_PORT}/ace_tools/call_function",
        json=MethodCall(
            request_id=str(uuid.uuid4()),
            object_reference=ObjectReference(type="callbacks", id=os.environ["KERNEL_CALLBACK_ID"]),
            method=function_name,
            args=list(function_args),
            kwargs=function_kwargs,
        ).model_dump(),
    )

    if response.status_code == 200:
        return response.json().get("value")
    else:
        raise RuntimeError(
            f"Error calling callback {function_name}: status_code={response.status_code}, {response.text}"
        )


def log_exception(
    message: str,
    exception_id: str | None = None,
    func_name: str | None = None,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> None:
                                                                
     
                                                                                    
                                                                                          
                                                                                    
     
            
                                   
     
              
                   
                           
                                                      
    exception_id = exception_id or str(uuid.uuid4())
    exc_type, exc_value, _exc_traceback = sys.exc_info()
    traceback_str = "".join(traceback.format_exc())

    args_str = None
    kwargs_str = None

    if args:
        try:
            args_str = str(args)
        except Exception:
            args_str = "failed_to_serialize"

    if kwargs:
        try:
            kwargs_str = str(kwargs)
        except Exception:
            kwargs_str = "failed_to_serialize"

    requests.post(
        f"{_BASE_URL}:{_USER_MACHINE_PORT}/ace_tools/log_exception",
        json={
            "message": message,
            "exception": {
                "id": exception_id,
                "type": exc_type.__name__,
                "value": str(exc_value),
                "traceback": traceback_str,
            },
            "orig_func_name": func_name,
            "orig_func_args": args_str,
            "orig_func_kwargs": kwargs_str,
        },
    )


def log_matplotlib_img_fallback(reason: str, metadata: dict[str, Any] | None = None) -> None:
                                                                                     
                                                  
     
                                                                                      
                                    
    requests.post(
        f"{_BASE_URL}:{_USER_MACHINE_PORT}/ace_tools/log_matplotlib_img_fallback",
        json={
            "reason": reason,
            "metadata": metadata,
        },
    )


def display_dataframe_to_user(name: str, dataframe: pd.DataFrame) -> pd.DataFrame:
                                                   
    if os.getenv("FEATURE_SET") == "chatgpt-research":
        return dataframe.head()

                                                                                               
    file_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    modified_csv_path = f"/mnt/data/{file_name}.csv"

                                                
                                                                                     
    if isinstance(dataframe.index, pd.RangeIndex):
        dataframe.to_csv(modified_csv_path, index=False)
    else:
                                                 
        dataframe.to_csv(modified_csv_path)

    _call_function("display_dataframe_to_user", [], {"path": modified_csv_path, "title": name})
    return dataframe.head()


def display_chart_to_user(path: str, title: str, chart_type: str) -> None:
                                                   
    if os.getenv("FEATURE_SET") == "chatgpt-research":
        return

    _call_function(
        "display_chart_to_user", [], {"path": path, "title": title, "chart_type": chart_type}
    )


def display_matplotlib_image_to_user(
    title: str,
    reason: str,
    exception_ids: list[str],
) -> None:
    _call_function(
        "display_matplotlib_image_to_user",
        [],
        {
            "title": title,
            "reason": reason,
            "exception_ids": exception_ids,
        },
    )
