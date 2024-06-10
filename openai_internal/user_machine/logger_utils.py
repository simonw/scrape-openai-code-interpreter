import logging
import os
from datetime import datetime, timezone
from typing import Any

from pythonjsonlogger import jsonlogger

PLAINTEXT_LOG_FORMAT = "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s"


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(
        self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]
    ) -> Any:
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
                                                                    
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_record["timestamp"] = now
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def init_logger_settings(
    root_log_level: int | str = logging.INFO,
    force_text_formatter: bool = False,
):
    env = os.getenv("ENVIRONMENT")
    base_handler = logging.StreamHandler()

    if env == "development" or force_text_formatter:
        text_formatter = logging.Formatter(PLAINTEXT_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
        base_handler.setFormatter(text_formatter)
    else:
        json_formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
        base_handler.setFormatter(json_formatter)

                                    
    root_logger = logging.getLogger()
    root_logger.setLevel(root_log_level)
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    root_logger.addHandler(base_handler)
