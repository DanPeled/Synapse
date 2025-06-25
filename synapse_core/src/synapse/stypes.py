from typing import List, Union

from cv2 import Mat
from numpy import ndarray

#: A video frame, represented either as an OpenCV Mat or a NumPy ndarray.
Frame = Union[Mat, ndarray]

#: A general-purpose data value that can be a number, boolean, string,
#: or a list of these primitive types.
DataValue = Union[float, bool, int, str, List[bool], List[float], List[str], List[int]]

#: An integer identifier for a specific camera.
CameraID = int

#: An integer identifier for a specific image processing pipeline.
PipelineID = int

#: A string name used to identify a pipeline.
PipelineName = str

PipelineTypeName = str
