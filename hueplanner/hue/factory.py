from .v1.client import HueBridgeV1
from .v2.client import HueBridgeV2


class HueBridgeFactory:
    def __init__(self, address: str, access_token: str) -> None:
        self.address: str = address
        self.access_token: str = access_token

    def api_v2(self) -> HueBridgeV2:
        return HueBridgeV2(address=self.address, access_token=self.access_token)

    def api_v1(self) -> HueBridgeV1:
        return HueBridgeV1(address=self.address, access_token=self.access_token)
