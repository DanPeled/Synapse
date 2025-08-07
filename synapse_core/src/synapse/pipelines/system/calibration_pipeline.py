from typing import Optional, Sequence

import cv2
from cv2.typing import MatLike
from synapse import Pipeline, PipelineSettings
from synapse.core.pipeline import systemPipeline
from synapse.core.settings_api import (BooleanConstraint, EnumeratedConstraint,
                                       NumberConstraint, settingField)
from synapse.stypes import Frame


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
    take_picture = settingField(BooleanConstraint(), default=False)


@systemPipeline()
class CalibrationPipeline(Pipeline[CalibrationPipelineSettings]):
    def __init__(self, settings: CalibrationPipelineSettings):
        super().__init__(settings)

        self._last_settings = {}
        self._update_board()

        self.detector_params = cv2.aruco.DetectorParameters()

        self.all_corners = []
        self.all_ids = []
        self.all_imgs = 0

        self.camera_matrix = None
        self.dist_coeffs = None
        self.calibrated = False

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

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, aruco_dict_name)
        )
        self.charuco_board = cv2.aruco.CharucoBoard(
            size=(int(squares_x), int(squares_y)),
            squareLength=square_length,
            markerLength=marker_length,
            dictionary=self.aruco_dict,
        )
        print(f"Updated Charuco board and dictionary: {current_settings}")

    def processFrame(self, img, timestamp: float) -> Frame:
        self._update_board()

        if not self.getSetting(self.settings.take_picture):
            return img

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.detector_params
        )

        if ids is not None and len(ids) > 0:
            img = cv2.aruco.drawDetectedMarkers(img, corners, ids)

        retval: Optional[int] = None
        charuco_corners: Optional[Sequence[MatLike]] = None
        charuco_ids: Optional[MatLike] = None
        if ids is not None and len(ids) > 0:
            retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                markerCorners=corners,
                markerIds=ids,
                image=gray,
                board=self.charuco_board,
            )

            if charuco_corners is not None and charuco_ids is not None:
                img = cv2.aruco.drawDetectedMarkers(
                    img,
                    borderColor=(100, 100, 100),
                    corners=charuco_corners,
                    ids=charuco_ids,
                )

        total_corners = (self.getSetting(self.settings.squares_x) - 1) * (
            self.getSetting(self.settings.squares_y) - 1
        )
        min_corners_required = int(total_corners * 0.7)

        if retval is not None and retval >= min_corners_required:
            self.all_corners.append(charuco_corners)
            self.all_ids.append(charuco_ids)
            self.all_imgs += 1

            ...

        # Visual feedback text
        text = f"Corners detected: {retval if retval is not None else 0} / {total_corners} (min {min_corners_required})"
        cv2.putText(
            img,
            text,
            org=(10, 30),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=0.7,
            color=(0, 255, 0)
            if retval and retval >= min_corners_required
            else (0, 0, 255),
            thickness=2,
            lineType=cv2.LINE_AA,
        )

        if self.all_imgs >= self.getSetting(self.settings.calibration_images_count):
            self._calibrate_camera(gray.shape[::-1])
            self.calibrated = True
            print("Calibration completed!")

            self.all_corners = []
            self.all_ids = []
            self.all_imgs = 0
            self.setSetting(self.settings.take_picture, False)

        return img

    def _calibrate_camera(self, image_size):
        (
            ret,
            camera_matrix,
            dist_coeffs,
            rvecs,
            tvecs,
            std_intrinsics,
            std_extrinsics,
            per_view_errors,
        ) = cv2.aruco.calibrateCameraCharucoExtended(
            charucoCorners=self.all_corners,
            charucoIds=self.all_ids,
            board=self.charuco_board,
            imageSize=image_size,
            cameraMatrix=cv2.UMat(),
            distCoeffs=cv2.UMat(),
            flags=0,
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6),
        )

        if ret:
            self.camera_matrix = camera_matrix
            self.dist_coeffs = dist_coeffs
            print("Camera matrix:\n", camera_matrix)
            print("Distortion coefficients:\n", dist_coeffs)
        else:
            print("Calibration failed.")
