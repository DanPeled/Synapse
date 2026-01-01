# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Tuple, Union

from cv2 import Mat
from numpy import ndarray

#: A video frame, represented either as an OpenCV Mat or a NumPy ndarray.
Frame = Union[Mat, ndarray]

#: A general-purpose data value that can be a number, boolean, string,
#: or a list of these primitive types.
DataValue = Union[float, bool, int, str, List[bool], List[float], List[str], List[int]]

#: An integer identifier for a specific camera.
CameraID = int

#: String static identifier for a camera
CameraUID = str

CameraName = str

#: An integer identifier for a specific image processing pipeline.
PipelineID = int

#: A string name used to identify a pipeline.
PipelineName = str

PipelineTypeName = str

Resolution = Tuple[int, int]

RecordingFilename = str
RecordingStatus = bool
