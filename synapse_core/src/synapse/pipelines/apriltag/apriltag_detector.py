# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

from typing_extensions import Buffer

Homography = Tuple[float, float, float, float, float, float, float, float, float]
Corners = Tuple[float, float, float, float, float, float, float, float]


def makeCorners(
    x0: float = 0.0,
    y0: float = 0.0,
    x1: float = 0.0,
    y1: float = 0.0,
    x2: float = 0.0,
    y2: float = 0.0,
    x3: float = 0.0,
    y3: float = 0.0,
) -> Corners:
    """
    Constructs a Corners tuple with 8 float values.
    Defaults to all zeros if no arguments are provided.
    """
    return (x0, y0, x1, y1, x2, y2, x3, y3)


@dataclass(frozen=True)
class AprilTagDetection:
    tagID: int
    homography: Homography
    corners: Corners


class AprilTagDetector(ABC):
    @dataclass
    class Config:
        numThreads: int = 1
        refineEdges: bool = True
        quadDecimate: float = 2.0
        quadSigma: float = 0.0

    @abstractmethod
    def detect(self, frame: Buffer) -> List[AprilTagDetection]: ...

    @abstractmethod
    def addFamily(self, fam: str) -> None: ...

    @abstractmethod
    def setConfig(self, config: Config) -> None: ...
