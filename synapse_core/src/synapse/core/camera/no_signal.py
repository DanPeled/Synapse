from typing import List, Optional, Tuple, Union

from synapse.stypes import CameraID, Frame, Resolution

from ...stypes import PropertyMetaDict, Size
from .synapse_camera import SynapseCamera


class NoSignalCamera(SynapseCamera):
    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.resolution: Resolution = (640, 480)

    @classmethod
    def create(
        cls, *_, path: Union[str, int] = 0, name: str = "", index: CameraID = -1
    ) -> "NoSignalCamera":
        inst = NoSignalCamera(name)
        inst.setIndex(index)
        return inst

    def grabFrame(self) -> Tuple[bool, Optional[Frame]]:
        # Always return a no-signal frame
        return True, self.generateNoSignalFrame(self.resolution)

    def isConnected(self) -> bool:
        # Pretend the camera is never connected
        return False

    def close(self) -> None:
        pass

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        # Ignore all property changes
        pass

    def getProperty(self, prop: str) -> Union[int, float, None]:
        # No properties exist
        return None

    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        # Only store resolution for frame generation
        self.resolution = (width, height)

    def getResolution(self) -> Size:
        return self.resolution

    def getSupportedResolutions(self) -> List[Size]:
        # Only support the current resolution
        return [self.resolution]

    def getPropertyMeta(self) -> Optional[PropertyMetaDict]:
        return None

    def getMaxFPS(self) -> float:
        return 0.0
