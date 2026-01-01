# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, NamedTuple, Optional, Sequence

import cv2
import numpy as np
from cv2.aruco import Dictionary
from synapse import Pipeline, PipelineSettings
from synapse.core.camera_factory import CalibrationData
from synapse.core.pipeline import (CameraSettings, FrameResult, PipelineResult,
                                   systemPipeline)
from synapse.core.settings_api import (BooleanConstraint, EnumeratedConstraint,
                                       NumberConstraint, settingField)
from synapse.core.synapse import RemovePipelineMessageProto, Synapse
from synapse_net.proto.v1 import (CalibrationDataProto, MessageProto,
                                  MessageTypeProto)


class CalibrationResult(NamedTuple):
    mean_error: float
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    rvecs: Sequence[np.ndarray]
    tvecs: Sequence[np.ndarray]


class CalibrationPipelineSettings(PipelineSettings):
    squares_x = settingField(
        NumberConstraint(minValue=1, maxValue=None, step=1),
        default=5,
        description="Number of squares in the X direction (width)",
    )
    squares_y = settingField(
        NumberConstraint(minValue=1, maxValue=None, step=1),
        default=7,
        description="Number of squares in the Y direction (height)",
    )
    square_length = settingField(
        NumberConstraint(minValue=0.001, maxValue=None, step=0.001),
        default=0.04,
        description="Physical length of one square side (in meters)",
    )
    marker_length = settingField(
        NumberConstraint(minValue=0.001, maxValue=None, step=0.001),
        default=0.02,
        description="Physical length of the Aruco marker side inside the square (in meters)",
    )
    calibration_images_count = settingField(
        NumberConstraint(minValue=5, maxValue=100, step=1),
        default=20,
        description="Number of images to capture for calibration",
    )
    board_dictionary = settingField(
        EnumeratedConstraint(
            [
                "DICT_4X4_50",
                "DICT_4X4_100",
                "DICT_4X4_250",
                "DICT_4X4_1000",
                "DICT_5X5_50",
                "DICT_5X5_100",
                "DICT_5X5_250",
                "DICT_5X5_1000",
                "DICT_6X6_50",
                "DICT_6X6_100",
                "DICT_6X6_250",
                "DICT_6X6_1000",
                "DICT_7X7_50",
                "DICT_7X7_100",
                "DICT_7X7_250",
                "DICT_7X7_1000",
                "DICT_ARUCO_ORIGINAL",
            ]
        ),
        default="DICT_5X5_1000",
        description="Aruco dictionary type used for the Charuco board",
    )
    take_picture = settingField(BooleanConstraint(renderAsButton=True), default=False)


@systemPipeline()
class CalibrationPipeline(Pipeline[CalibrationPipelineSettings, PipelineResult]):
    def __init__(self, settings: CalibrationPipelineSettings):
        super().__init__(settings)

        self._last_settings = {}
        self._update_board()

        self.detector_params = cv2.aruco.DetectorParameters()

        self.all_corners: List = []
        self.all_ids: List = []
        self.all_imgs: int = 0

        self.camera_matrix = None
        self.dist_coeffs = None
        self.calibrated = False
        self.imageSize: Optional[List] = None

    def _update_board(self):
        squares_x = self.getSetting(self.settings.squares_x)
        squares_y = self.getSetting(self.settings.squares_y)
        square_length = self.getSetting(self.settings.square_length)
        marker_length = self.getSetting(self.settings.marker_length)
        aruco_dict_name = self.getSetting(self.settings.board_dictionary)

        current_settings = {
            "squares_x": squares_x,
            "squares_y": squares_y,
            "square_length": square_length,
            "marker_length": marker_length,
            "board_dictionary": aruco_dict_name,
        }

        if (
            current_settings == self._last_settings
            or squares_x <= 1
            or squares_y <= 1
            or square_length < marker_length
            or marker_length <= 0
        ):
            return

        self._last_settings = current_settings

        self.aruco_dict: Dictionary = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, aruco_dict_name)
        )
        self.charuco_board = cv2.aruco.CharucoBoard(
            size=(int(squares_x), int(squares_y)),
            squareLength=square_length,
            markerLength=marker_length,
            dictionary=self.aruco_dict,
        )

    def processFrame(self, img, timestamp: float) -> FrameResult:
        self._update_board()

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = cv2.aruco.detectMarkers(
            image=gray, dictionary=self.aruco_dict
        )

        total_pics = self.getSetting(self.settings.calibration_images_count)
        pics_taken = self.all_imgs
        pics_left = max(total_pics - pics_taken, 0)

        # Prepare text
        text = f"Pictures left: {pics_left} / {total_pics}"

        # Choose font, scale, color, thickness
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        color = (0, 255, 255)  # Yellow for visibility
        thickness = 2
        position = (10, 30)  # Top-left corner, with some margin

        # Put text on image
        img = cv2.putText(
            img, text, position, font, font_scale, color, thickness, cv2.LINE_AA
        )

        self.setDataValue("Pictures Left", f"{pics_left} / {total_pics}")

        img = cv2.aruco.drawDetectedMarkers(
            image=img,
            corners=corners,
            borderColor=(
                0,
                255,
                0,
            ),
        )

        if ids is not None and len(ids) > 0:
            response, charuco_corners, charuco_ids = (
                cv2.aruco.interpolateCornersCharuco(
                    markerCorners=corners,
                    markerIds=ids,
                    image=gray,
                    board=self.charuco_board,
                )
            )

            min_ratio = 0.5  # require at least 50% of corners
            total_corners = (
                self.charuco_board.getChessboardSize()[0]
                * self.charuco_board.getChessboardSize()[1]
            )
            required_corners = int(total_corners * min_ratio)

            if response >= required_corners:
                start_x = 10
                start_y = img.shape[0] - 30

                # Define points for checkmark
                pt1 = (start_x, start_y)
                pt2 = (start_x + 10, start_y + 15)
                pt3 = (start_x + 30, start_y - 10)

                check_color = (0, 255, 0)  # Green
                thickness = 5

                cv2.line(img, pt1, pt2, check_color, thickness)
                cv2.line(img, pt2, pt3, check_color, thickness)
                self.setDataValue("Can Take Picture", True)

                if self.getSetting(self.settings.take_picture):
                    self.all_corners.append(charuco_corners)
                    self.all_ids.append(charuco_ids)
                    self.all_imgs += 1

                    self.setSetting(self.settings.take_picture, False)

                img = cv2.aruco.drawDetectedCornersCharuco(
                    image=img, charucoCorners=charuco_corners, charucoIds=charuco_ids
                )

                if not self.imageSize:
                    self.imageSize = gray.shape[::-1]
            else:
                self.setDataValue("Can Take Picture", False)
        else:
            self.setDataValue("Can Take Picture", False)

        if (
            self.all_imgs > self.getSetting(self.settings.calibration_images_count)
            and not self.calibrated
        ):
            if self.imageSize:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
                flags = 0

                Synapse.kInstance.websocket.sendToAllSync(
                    MessageProto(
                        type=MessageTypeProto.CALIBRATING,
                        remove_pipeline=RemovePipelineMessageProto(
                            cameraid=self.cameraIndex,
                            remove_pipeline_index=self.pipelineIndex,
                        ),
                    ).SerializeToString()
                )

                retval, cameraMatrix, distCoeffs, _, _ = (
                    cv2.aruco.calibrateCameraCharuco(
                        self.all_corners,  # List[np.ndarray]
                        self.all_ids,  # List[np.ndarray]
                        self.charuco_board,  # CharucoBoard object
                        self.imageSize,  # Tuple[int, int]
                        np.empty((0, 0)),  # cameraMatrix initial guess
                        np.empty((0, 0)),  # distCoeffs initial guess
                        flags=flags,
                        criteria=criteria,
                    )
                )

                flattenedMatrix = cameraMatrix.flatten().tolist()
                flattendDistCoeffs = distCoeffs.flatten().tolist()

                Synapse.kInstance.websocket.sendToAllSync(
                    MessageProto(
                        type=MessageTypeProto.CALIBRATION_DATA,
                        calibration_data=CalibrationDataProto(
                            camera_index=self.cameraIndex,
                            mean_error=retval,
                            camera_matrix=flattenedMatrix,
                            dist_coeffs=flattendDistCoeffs,
                            resolution=self.getCameraSetting(CameraSettings.resolution),
                        ),
                    ).SerializeToString()
                )
                resolution = self.getCameraSetting(CameraSettings.resolution).split("x")
                width = int(resolution[0])
                height = int(resolution[1])

                Synapse.kInstance.runtimeHandler.cameraHandler.cameraConfigBindings[
                    self.cameraIndex
                ].calibration[
                    self.getCameraSetting(CameraSettings.resolution)
                ] = CalibrationData(
                    matrix=cameraMatrix.flatten().tolist(),
                    distCoeff=distCoeffs.flatten().tolist(),
                    measuredRes=(width, height),
                    meanErr=retval,
                )

                Synapse.kInstance.runtimeHandler.save()

                self.all_imgs = 0
                self.all_corners = []
                self.all_ids = []

                self.calibrated = True

        return img
