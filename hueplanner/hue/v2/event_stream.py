from __future__ import annotations

import json

import aiohttp
import structlog

from .models import HueEvent

logger = structlog.getLogger(__name__)


class HueEventStream:
    EXPECTED_INTRO = ": hi"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._init_msg = True
        self._stream_resp: aiohttp.ClientResponse | None = None

    async def _init_stream(self):
        resp = await self._session.get("/eventstream/clip/v2", headers={"Accept": "text/event-stream"})
        resp.raise_for_status()
        self._stream_resp = resp

    async def close(self):
        if self._stream_resp:
            await self._stream_resp.release()  # Explicitly release the response
            self._stream_resp = None
        await self._session.close()

    async def __aenter__(self):
        try:
            await self._init_stream()
        except Exception:
            await self.close()
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._stream_resp:
            raise StopAsyncIteration  # Stop iteration if there's no stream response
        try:
            buf = b""
            async for data, end_of_http_chunk in self._stream_resp.content.iter_chunks():
                buf += data
                if end_of_http_chunk:
                    result = await self.process_chunk(buf)
                    if result is not None:
                        return result
                    buf = b""
        except aiohttp.ClientConnectionError:
            raise StopAsyncIteration
        except Exception as e:
            raise Exception("Failed to fetch next event") from e  # Stop iteration on error
        raise StopAsyncIteration  # Raise StopAsyncIteration to end the iteration

    async def process_chunk(self, data):
        data = data.decode().strip()
        if self._init_msg:
            if data != self.EXPECTED_INTRO:
                raise Exception(f"Unknown welcome message. Received: {data!r}, Expected: {self.EXPECTED_INTRO!r}")
            self._init_msg = False
            return None
        id_part, data_part = data.split("\n")
        event_id = id_part.split(": ", 1)[1]
        raw_json_data = data_part.split(": ", 1)[1]
        json_data = json.loads(raw_json_data)
        logger.debug("Received event:", id=event_id, data=json_data)
        return HueEvent(id=event_id, data=json_data)
