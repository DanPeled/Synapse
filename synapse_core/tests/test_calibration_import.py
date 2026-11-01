# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from synapse.core.camera_factory import CalibrationData, CameraConfig
from synapse.core.config import Config
from synapse.core.synapse import Synapse
from synapse_net.generated.messages.v1 import (ImportCalibrationMessageProto,
                                               MessageProto, MessageTypeProto)

CALIBDB_JSON = {
    "avg_reprojection_error": 0.42,
    "camera_matrix": [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]],
    "distortion_coefficients": [0.1, -0.2, 0.0, 0.0, 0.05],
    "img_size": [1280, 720],
}

CALIBDB_UI_SAMPLE = {
    "camera": "Integrated Camera (04f2:b221)",
    "platform": "Windows NT 10.0; Win64; x64",
    "avg_reprojection_error": 0.29046828629127375,
    "camera_matrix": [
        [997.2004468512075, 0, 632.9006210418327],
        [0, 995.8634526747086, 333.73221285398995],
        [0, 0, 1],
    ],
    "distortion_coefficients": [
        -0.11581000858261808,
        0.28621752935035355,
        0.00034019588183455514,
        -0.0010081448912734748,
        -0.24207132830769904,
    ],
    "distortion_model": "rectilinear",
    "img_size": [1280, 720],
    "calibration_time": "Sat, 20 Jan 2024 21:29:18 GMT",
}


class TestCalibrationDataFromJson(unittest.TestCase):
    def test_reads_calibdb_file(self) -> None:
        calibration, resolution = CalibrationData.fromCalibDbJson(CALIBDB_JSON)

        self.assertEqual(resolution, "1280x720")
        self.assertEqual(calibration.measuredRes, (1280, 720))
        self.assertEqual(calibration.meanErr, 0.42)
        self.assertEqual(
            calibration.matrix,
            [1000.0, 0.0, 640.0, 0.0, 1000.0, 360.0, 0.0, 0.0, 1.0],
        )
        self.assertEqual(calibration.distCoeff, [0.1, -0.2, 0.0, 0.0, 0.05])

    def test_uses_fallback_resolution_for_flat_file(self) -> None:
        data = {
            "cameraMatrix": [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
            "distCoeffs": [0.1, -0.2, 0.0, 0.0, 0.05],
        }

        calibration, resolution = CalibrationData.fromCalibDbJson(data, "640x480")

        self.assertEqual(resolution, "640x480")
        self.assertEqual(calibration.meanErr, 0.0)

    def test_reads_calibdb_sample_from_ui(self) -> None:
        calibration, resolution = CalibrationData.fromCalibDbJson(CALIBDB_UI_SAMPLE)

        self.assertEqual(resolution, "1280x720")
        self.assertEqual(calibration.measuredRes, (1280, 720))
        self.assertAlmostEqual(calibration.meanErr, 0.29046828629127375)
        self.assertEqual(len(calibration.matrix), 9)
        self.assertEqual(len(calibration.distCoeff), 5)

    def test_reads_opencv_matrix_objects(self) -> None:
        data = {
            "camera_matrix": {
                "rows": 3,
                "cols": 3,
                "data": [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
            },
            "distortion_coefficients": {"rows": 1, "cols": 2, "data": [0.1, -0.2]},
            "img_size": [1280, 720],
        }

        calibration, resolution = CalibrationData.fromCalibDbJson(data)

        self.assertEqual(resolution, "1280x720")
        self.assertEqual(len(calibration.matrix), 9)
        self.assertEqual(calibration.distCoeff, [0.1, -0.2])

    def test_requires_resolution_when_file_has_no_image_size(self) -> None:
        data = {
            "camera_matrix": [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
            "distortion_coefficients": [0.1, -0.2],
        }

        with self.assertRaisesRegex(ValueError, "no image size"):
            CalibrationData.fromCalibDbJson(data)

    def test_rejects_invalid_camera_matrix(self) -> None:
        data = {
            "camera_matrix": [1000, 0, 640],
            "distortion_coefficients": [0.1, -0.2],
            "img_size": [1280, 720],
        }

        with self.assertRaisesRegex(ValueError, "exactly 9 values"):
            CalibrationData.fromCalibDbJson(data)


class TestImportCalibration(unittest.TestCase):
    def setUp(self) -> None:
        self.tempDir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempDir.name)
        configDir = self.root / "config"
        configDir.mkdir()
        self.configPath = configDir / "settings.yml"
        self.configPath.write_text("global:\n  cameras: []\n", encoding="utf-8")

        self.config = Config()
        self.config.load(self.configPath)

        self.cameraConfig = CameraConfig(
            name="Test Camera",
            id="test-camera",
            calibration={},
            defaultPipeline=0,
            streamRes=(640, 480),
        )
        self.runtimeHandler = MagicMock()
        self.runtimeHandler.cameraHandler.cameraConfigBindings = {0: self.cameraConfig}
        self.runtimeHandler.pipelineBindings = {}
        self.runtimeHandler.pipelineHandler.getPipeline.return_value = None
        self.websocket = MagicMock()

        self.synapse = Synapse.__new__(Synapse)
        self.synapse.runtimeHandler = self.runtimeHandler
        self.synapse.websocket = self.websocket

        self.importDir = self.root / ".calibration_import"
        self.importDir.mkdir()

    def tearDown(self) -> None:
        self.tempDir.cleanup()

    def writeImportFile(self, data: object) -> str:
        (self.importDir / "camera_0.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        return ".calibration_import/camera_0.json"

    def test_imports_uploaded_file_and_broadcasts_calibration(self) -> None:
        data = dict(CALIBDB_JSON)
        data.pop("img_size")
        filePath = self.writeImportFile(data)

        imported = self.synapse.importCalibration(0, filePath)

        self.assertTrue(imported)
        self.assertIn("640x480", self.cameraConfig.calibration)
        self.assertFalse((self.root / filePath).exists())
        self.runtimeHandler.save.assert_called_once()

        message = MessageProto().parse(self.websocket.sendToAllSync.call_args.args[0])
        self.assertEqual(message.type, MessageTypeProto.CALIBRATION_DATA)
        self.assertEqual(message.calibration_data.camera_index, 0)
        self.assertEqual(message.calibration_data.resolution, "640x480")

    def test_explicit_resolution_is_used_as_fallback(self) -> None:
        data = dict(CALIBDB_JSON)
        data.pop("img_size")
        filePath = self.writeImportFile(data)

        imported = self.synapse.importCalibration(0, filePath, "1280x720")

        self.assertTrue(imported)
        self.assertIn("1280x720", self.cameraConfig.calibration)

    def test_message_dispatches_to_import(self) -> None:
        filePath = self.writeImportFile(CALIBDB_UI_SAMPLE)
        message = MessageProto(
            type=MessageTypeProto.IMPORT_CALIBRATION,
            import_calibration=ImportCalibrationMessageProto(
                camera_index=0, file_path=filePath
            ),
        )

        self.synapse.onMessage(None, message.SerializeToString())

        self.assertIn("1280x720", self.cameraConfig.calibration)
        self.runtimeHandler.save.assert_called_once()

    def test_active_pipeline_resolution_is_used_as_fallback(self) -> None:
        pipeline = MagicMock()
        pipeline.getCameraSetting.return_value = "1280x720"
        self.runtimeHandler.pipelineBindings = {0: 1}
        self.runtimeHandler.pipelineHandler.getPipeline.return_value = pipeline

        self.assertEqual(self.synapse.getCalibrationResolution(0), "1280x720")

    def test_invalid_json_does_not_replace_calibration(self) -> None:
        (self.importDir / "camera_0.json").write_text("not json", encoding="utf-8")

        with patch("synapse.core.synapse.err"):
            imported = self.synapse.importCalibration(
                0, ".calibration_import/camera_0.json"
            )

        self.assertFalse(imported)
        self.assertEqual(self.cameraConfig.calibration, {})
        self.runtimeHandler.save.assert_not_called()
        self.websocket.sendToAllSync.assert_not_called()
        self.assertFalse((self.importDir / "camera_0.json").exists())


if __name__ == "__main__":
    unittest.main()
