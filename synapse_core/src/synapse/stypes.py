from typing import List, Union

from cv2 import Mat
from numpy import ndarray

Frame = Union[Mat, ndarray]
DataValue = Union[float, bool, int, str, List[bool], List[float], List[str], List[int]]
CameraID = int
PipelineID = int
PipelineName = str
