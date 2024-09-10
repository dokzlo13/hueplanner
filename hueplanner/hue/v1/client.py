from __future__ import annotations

from typing import Any

import aiohttp
import structlog
import yarl

from .models import Group, Light, Scene

logger = structlog.getLogger(__name__)


class HueBridgeV1:
    def __init__(self, address: str, access_token: str) -> None:
        self.address: yarl.URL = yarl.URL(f"http://{address}" if not address.startswith("http") else address)
        self.access_token = access_token
        self._session: aiohttp.ClientSession | None = None

    @property
    def _api_url(self) -> yarl.URL:
        return yarl.URL(f"/api/{self.access_token}")

    def _new_session(self, **kwargs) -> aiohttp.ClientSession:
        base_url = self.address.with_scheme("http")
        return aiohttp.ClientSession(
            base_url=base_url,
            **kwargs,
        )

    async def __aenter__(self):
        await self.connect()

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def connect(self):
        self._session = self._new_session()
        resp = await self._session.get(self._api_url / "capabilities")
        resp.raise_for_status()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise Exception("Not connected")
        return self._session

    async def get_group(self, group_id: int | str) -> Group:
        resp = await self.session.get(self._api_url / f"groups/{group_id}")
        resp.raise_for_status()
        model = Group.model_validate(await resp.json())
        model.id = int(group_id)
        return model

    async def get_scenes(self) -> list[Scene]:
        resp = await self.session.get(self._api_url / "scenes")
        resp.raise_for_status()
        items = []
        for k, v in (await resp.json()).items():
            model = Scene.model_validate(v)
            model.id = k
            items.append(model)
        return items

    async def get_lights(self) -> list[Light]:
        resp = await self.session.get(self._api_url / "lights")
        resp.raise_for_status()
        items = []
        for k, v in (await resp.json()).items():
            model = Light.model_validate(v)
            model.id = int(k)
            items.append(model)
        return items

    async def get_groups(self) -> list[Group]:
        resp = await self.session.get(self._api_url / "groups")
        resp.raise_for_status()
        items = []
        for k, v in (await resp.json()).items():
            model = Group.model_validate(v)
            model.id = int(k)
            items.append(model)
        return items

    async def send_group_action(self, group_id: int | str, action: dict[str, Any]):
        resp = await self.session.put(
            self._api_url / f"groups/{group_id}/action",
            json=action,
        )
        resp.raise_for_status()
        return await resp.json()

    async def activate_scene(self, group_id: int | str, scene_id: str, transition_time: int | None = None):
        body: dict[str, Any] = {
            "scene": scene_id,
        }
        if transition_time:
            body["transitiontime"] = transition_time

        resp = await self.session.put(
            self._api_url / f"groups/{group_id}/action",
            json=body,
        )
        resp.raise_for_status()
        return await resp.json()
