import asyncio
import logging
import time
import traceback
from typing import NoReturn

from jupyter_client.manager import AsyncKernelManager
from jupyter_client.multikernelmanager import AsyncMultiKernelManager

from . import run_jupyter


class HealthCheckBackgroundJob:
                                                                                
                                                                               
                                                        
    last_success_at: float | None
    last_error: str | None
    code: str
                                                                               
                       
    health_check_delay: int = 300
                                                                                
                                              
    health_check_failure_threshold: int = 600
    logger: logging.Logger
    multi_kernel_manager: AsyncMultiKernelManager

    def __init__(
        self,
        *,
        code: str | None = None,
        logger: logging.Logger,
        kernel_manager: AsyncMultiKernelManager,
    ):
        self.last_success_at = None
        self.last_error = None
        if code is not None:
            self.code = code
        else:
            self.code = "print(f'{400+56}'); 100+23"
        self.logger = logger
        self.multi_kernel_manager = kernel_manager

    def is_stale(self) -> bool:
        if self.last_success_at is None:
            return True
        last_success_age = time.monotonic() - self.last_success_at
        return last_success_age > self.health_check_failure_threshold

    async def run(self) -> NoReturn:
        while True:
            start_time = time.monotonic()
            try:
                await self.run_once()
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
                self.logger.debug(f"Health check: completed successfully in {elapsed_time} seconds")
            except Exception:
                self.last_error = traceback.format_exc()
                self.logger.error(f"Health check: encountered error:\n{self.last_error}")

            await asyncio.sleep(self.health_check_delay)

    async def run_once(self) -> None:
        self.logger.debug("Health check: running...")

        kernel_id = await self.multi_kernel_manager.start_kernel()
        km = self.multi_kernel_manager.get_kernel(kernel_id)
        assert isinstance(km, AsyncKernelManager)
        try:
            result = await run_jupyter.async_run_code(km, self.code, shutdown_kernel=False)
            execute_result, error_stacktrace, stream_text = result
            if error_stacktrace is not None:
                self.logger.info(
                    f"Health check: code execution got unexpected error:\n{error_stacktrace}"
                )
                self.last_error = error_stacktrace
            elif execute_result != {"text/plain": "123"} or stream_text != "456\n":
                s = f"Health check: code execution got unexpected result: [{execute_result}] [{stream_text}]"
                self.logger.info(s)
                self.last_error = s
            else:
                self.last_success_at = time.monotonic()
                self.last_error = None
        finally:
            await self.multi_kernel_manager.shutdown_kernel(kernel_id)
