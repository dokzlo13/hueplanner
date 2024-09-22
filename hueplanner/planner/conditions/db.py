import structlog
from pydantic.dataclasses import dataclass

from hueplanner.ioc import IOC
from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedCondition, PlanCondition

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanConditionDBKeyNotSet(PlanCondition, Serializable):
    db: str = "stored_scenes"
    db_key: str

    async def define_condition(self, storage: IKeyValueStorage) -> EvaluatedCondition:
        async def check():
            db = await storage.create_collection(self.db)
            return not (await db.contains(self.db_key))

        return check
