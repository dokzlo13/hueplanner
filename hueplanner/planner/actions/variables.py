from __future__ import annotations

import structlog
from pydantic.dataclasses import dataclass

from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionFlushDb(PlanAction, Serializable):
    db: str

    async def define_action(self, storage: IKeyValueStorage) -> EvaluatedAction:
        async def action():
            logger.info("Flushing database requested", action=repr(self))
            db = await storage.create_collection(self.db)
            await db.delete_all()
            logger.info("Database data removed", name=self.db)

        return action
