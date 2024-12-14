from __future__ import annotations

import aiohttp
import structlog
import yarl

from .event_stream import HueEventStream
from .models.light import Light, LightGetResponse, LightUpdateRequest, LightUpdateResponse
from .models.scene import Scene, SceneGetResponse
from .models.zone import Zone, ZoneGetResponse

logger = structlog.getLogger(__name__)


class HueBridgeV2:
    def __init__(self, address: str, access_token: str) -> None:
        self.address: yarl.URL = yarl.URL(f"http://{address}" if not address.startswith("http") else address)
        self.access_token = access_token
        self._session: aiohttp.ClientSession | None = None

    def _new_session(self, **kwargs) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            base_url=self.address.with_scheme("https"),
            headers={"hue-application-key": self.access_token},
            connector=aiohttp.TCPConnector(ssl=False),
            **kwargs,
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise Exception("Not connected")
        return self._session

    async def __aenter__(self):
        await self.connect()

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def connect(self):
        self._session = self._new_session()
        resp = await self._session.get("/clip/v2/resource")
        resp.raise_for_status()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def get_lights(self) -> list[Light]:
        resp = await self.session.get("/clip/v2/resource/light")
        resp.raise_for_status()
        data = await resp.json()
        return LightGetResponse.model_validate(data).data

    async def get_light(self, id: str) -> Light:
        resp = await self.session.get(f"/clip/v2/resource/light/{id}")
        resp.raise_for_status()
        data = await resp.json()
        data = LightGetResponse.model_validate(data).data
        assert len(data) >= 1, "Not Found"
        return data[0]

    async def update_light(self, id: str, update: LightUpdateRequest) -> LightUpdateResponse:
        resp = await self.session.put(
            f"/clip/v2/resource/light/{id}",
            json=update.model_dump(exclude_none=True),
        )
        resp.raise_for_status()
        data = await resp.json()
        return LightUpdateResponse.model_validate(data)

    def event_stream(self) -> HueEventStream:
        return HueEventStream(
            self._new_session(
                timeout=aiohttp.ClientTimeout(
                    total=None,  # No total timeout
                    sock_connect=None,  # No socket connect timeout
                    sock_read=None,  # No socket read timeout
                )
            )
        )

    # FIXME: Under maintenance
    async def get_scenes(self) -> list[Scene]:
        resp = await self.session.get(
            "/clip/v2/resource/scene",
        )
        resp.raise_for_status()
        data = await resp.json()
        # TODO: proper error handling
        return SceneGetResponse.model_validate(data).data

    async def get_scene(self, id: str) -> Scene:
        resp = await self.session.get(
            f"/clip/v2/resource/scene/{id}",
        )
        resp.raise_for_status()
        data = await resp.json()
        # TODO: proper error handling
        data = SceneGetResponse.model_validate(data).data
        assert len(data) >= 1, "Not Found"
        return data[0]

    async def get_zones(self) -> list[Zone]:
        resp = await self.session.get(
            "/clip/v2/resource/zone",
        )
        resp.raise_for_status()
        data = await resp.json()
        return ZoneGetResponse.model_validate(data).data

    async def get_zone(self, id: str) -> Zone:
        resp = await self.session.get(
            f"/clip/v2/resource/zone/{id}",
        )
        resp.raise_for_status()
        data = await resp.json()
        # TODO: proper error handling
        data = ZoneGetResponse.model_validate(data).data
        assert len(data) >= 1, "Not Found"
        return data[0]

    # - - -

    async def get_grouped_lights(self):
        resp = await self.session.get(
            "/clip/v2/resource/grouped_light",
        )
        resp.raise_for_status()
        data = await resp.json()
        return data

    async def get_grouped_light(self, id: str):
        resp = await self.session.get(
            f"/clip/v2/resource/grouped_light/{id}",
        )
        resp.raise_for_status()
        data = await resp.json()
        return data

    async def get_devices(self):
        resp = await self.session.get(
            "/clip/v2/resource/device",
        )
        resp.raise_for_status()
        data = await resp.json()
        return data

    async def get_device(self, id: str):
        resp = await self.session.get(
            f"/clip/v2/resource/device/{id}",
        )
        resp.raise_for_status()
        data = await resp.json()
        return data
