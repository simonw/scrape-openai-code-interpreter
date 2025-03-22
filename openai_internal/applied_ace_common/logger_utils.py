import logging
import re


class AccessLogQueryParamRemover(logging.Formatter):
    query_param_pattern = re.compile(r"\?[^ ]*")

    def __init__(self, fmt=None, wrapped_formatter=None) -> None:
        if wrapped_formatter is None and fmt is None:
            raise ValueError("Either wrapped_formatter or fmt must be provided")

        if wrapped_formatter is None:
            wrapped_formatter = logging.Formatter(fmt=fmt)

        self.wrapped_formatter = wrapped_formatter

    def format(self, record):
        message = self.wrapped_formatter.format(record)
        message = self.query_param_pattern.sub("", message)
        return message


def redact_query_params(loggers: list[logging.Logger]) -> None:
    for logger in loggers:
        for handler in logger.handlers:
            handler.setFormatter(AccessLogQueryParamRemover(wrapped_formatter=handler.formatter))
