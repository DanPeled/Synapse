# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Union

import numpy as np
from cscore import VideoMode, VideoProperty

from ...stypes import CameraID, Frame, PropertyMetaDict, Size


class SynapseCamera(ABC):
    def __init__(self) -> None: ...

    @classmethod
    @abstractmethod
    def create(
        cls,
        *_,
        path: Union[str, int],
        index: CameraID,
    ) -> "SynapseCamera": ...

    @abstractmethod
    def grabFrame(self, buffer: np.ndarray) -> Tuple[float, Optional[Frame]]: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def isConnected(self) -> bool: ...

    @abstractmethod
    def setProperty(self, prop: str, value: Union[int, float]) -> None: ...

    @abstractmethod
    def getProperty(self, prop: str) -> Union[int, float, None]: ...

    def getProperties(self) -> List[VideoProperty]:
        return []

    @abstractmethod
    def setVideoMode(self, videoMode: VideoMode) -> None: ...

    @abstractmethod
    def getResolution(self) -> Size: ...

    @abstractmethod
    def getSupportedResolutions(self) -> List[Size]: ...

    @abstractmethod
    def getPropertyMeta(self) -> PropertyMetaDict: ...

    @abstractmethod
    def getMaxFPS(self) -> float: ...

    @abstractmethod
    def enumerateVideoModes(self) -> List[VideoMode]: ...

    @abstractmethod
    def getVideoMode(self) -> VideoMode: ...
