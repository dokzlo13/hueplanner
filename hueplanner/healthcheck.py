import asyncio
import typing

import structlog
from aiohttp import web

logger = structlog.getLogger(__name__)


class HealthcheckServer:
    def __init__(
        self, live_handler: typing.Callable, ready_handler: typing.Callable | None = None, context: typing.Any = None
    ) -> None:
        self._app = web.Application()
        if ready_handler is None:
            ready_handler = live_handler
        self._app.add_routes([web.get("/health/live", self._handler(live_handler, context))])
        self._app.add_routes([web.get("/health/ready", self._handler(ready_handler, context))])

    @staticmethod
    def _handler(callback: typing.Callable | typing.Awaitable, context: typing.Any):
        async def wrapped_handler(request):
            is_ok = False
            try:
                if asyncio.iscoroutinefunction(callback):
                    is_ok = await callback(context)
                else:
                    is_ok = callback(context)  # type: ignore
            except Exception as e:
                logger.exception("Health check probe failed", path=request.path)
                return web.json_response({"ok": False, "description": str(e)}, status=422)

            if is_ok:
                return web.json_response({"ok": True}, status=200)
            else:
                return web.json_response({"ok": False}, status=422)

        return wrapped_handler

    async def run(self, stop_event: asyncio.Event, host: str = "0.0.0.0", port: int = 9090) -> None:
        logger.debug("Starting health check server...")

        runner = web.AppRunner(self._app)
        await runner.setup()

        site = web.TCPSite(runner, host=host, port=port)
        await site.start()
        logger.info("Health check server started", host=host, port=port)
        await stop_event.wait()
        logger.debug("Stopping health check server...")

        await site.stop()
        await site._server.wait_closed()  # type: ignore
        logger.info("Health check server stopped")
