import asyncio
import json
import logging

import jupyter_client

       
                                      
           
                                                           
 
                                                          
                                                                                                                          
                                                                                                                    

logger = logging.getLogger(__name__)


class KernelDeath(Exception):
    pass


async def async_run_code(
    km: jupyter_client.AsyncKernelManager,
    code,
    *,
    interrupt_after=30,
    iopub_timeout=40,
    wait_for_ready_timeout=30,
    shutdown_kernel=True,
):
    assert iopub_timeout > interrupt_after
    try:

        async def get_iopub_msg_with_death_detection(
            kc: jupyter_client.AsyncKernelClient, *, timeout=None
        ):
            loop = asyncio.get_running_loop()
            dead_fut = loop.create_future()

            def restarting():
                assert (
                    False
                ), "Restart shouldn't happen because config.KernelRestarter.restart_limit is expected to be set to 0"

            def dead():
                logger.info("Kernel has died, will NOT restart")
                dead_fut.set_result(None)

            msg_task = asyncio.create_task(kc.get_iopub_msg(timeout=timeout))
            km.add_restart_callback(restarting, "restart")
            km.add_restart_callback(dead, "dead")
            try:
                done, _ = await asyncio.wait(
                    [dead_fut, msg_task], return_when=asyncio.FIRST_COMPLETED
                )
                if dead_fut in done:
                    raise KernelDeath()
                assert msg_task in done
                return await msg_task
            finally:
                msg_task.cancel()
                km.remove_restart_callback(restarting, "restart")
                km.remove_restart_callback(dead, "dead")

        async def send_interrupt():
            await asyncio.sleep(interrupt_after)
            logger.info("Sending interrupt to kernel")
            await km.interrupt_kernel()

        async def run():
            execute_result = None
            error_traceback = None
            stream_text_list = []
            kc = km.client()
            assert isinstance(kc, jupyter_client.AsyncKernelClient)
            kc.start_channels()
            try:
                await kc.wait_for_ready(timeout=wait_for_ready_timeout)
                msg_id = kc.execute(code)
                while True:
                    message = await get_iopub_msg_with_death_detection(kc, timeout=iopub_timeout)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(json.dumps(message, indent=2, default=str))
                    assert message["parent_header"]["msg_id"] == msg_id
                    msg_type = message["msg_type"]
                    if msg_type == "status":
                        if message["content"]["execution_state"] == "idle":
                            break
                    elif msg_type == "stream":
                        stream_name = message["content"]["name"]
                        stream_text = message["content"]["text"]
                        stream_text_list.append(stream_text)
                    elif msg_type == "execute_result":
                        execute_result = message["content"]["data"]
                    elif msg_type == "error":
                        error_traceback_lines = message["content"]["traceback"]
                        error_traceback = "\n".join(error_traceback_lines)
                    elif msg_type == "execute_input":
                        pass
                    else:
                        assert False, f"Unknown message_type: {msg_type}"
            finally:
                kc.stop_channels()
            return execute_result, error_traceback, "".join(stream_text_list)

        if interrupt_after:
            run_task = asyncio.create_task(run())
            send_interrupt_task = asyncio.create_task(send_interrupt())
            done, _ = await asyncio.wait(
                [run_task, send_interrupt_task], return_when=asyncio.FIRST_COMPLETED
            )
            if run_task in done:
                send_interrupt_task.cancel()
            else:
                assert send_interrupt_task in done
            result = await run_task
        else:
            result = await run()
        return result
    finally:
        if shutdown_kernel:
            await km.shutdown_kernel()
