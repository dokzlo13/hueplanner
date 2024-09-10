from __future__ import annotations

from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionFlushDb(PlanAction, Serializable):
    target_db: str

    class _Model(BaseModel):
        target_db: str

    async def define_action(self, storage: IKeyValueStorage) -> EvaluatedAction:
        async def action():
            logger.info("Flushing database requested", action=repr(self))
            db = await storage.create_collection(self.target_db)
            await db.delete_all()
            logger.info("Database data removed", name=self.target_db)

        return action
