# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import json
import math
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import cv2
import numpy as np
from cscore import VideoMode
from ntcore import NetworkTableInstance
from synapse.core.camera_factory import CameraConfig
from synapse.core.camera_handler import CameraHandler
from synapse.core.global_settings import GlobalSettings
from synapse.pipelines.apriltag.apriltag_robotpy import RobotpyApriltagDetector
from synapse_net.nt_client import NtClient
from synapse_sim.camera import SimCamera
from synapse_sim.model import (
    DEFAULT_CAMERA_OFFSET,
    DEFAULT_ROBOT_POSE,
    FIELD_OF_VIEW_DEGREES,
    SUPPORTED_RESOLUTIONS,
    cameraMatrix,
)
from synapse_sim.setup import installSimulation
from synapse_sim.three import L_METERS, W_METERS, camera_spec, wpi_camera_to_three
from synapse_sim.viewer import SimulationViewer, findChrome
from wpimath.geometry import Pose3d, Rotation3d, Translation3d

REPO_ROOT = Path(__file__).parents[2]
SIM_ASSETS = Path(__file__).parents[1] / "src" / "synapse_sim" / "assets"
TAG_ASSETS = SIM_ASSETS / "apriltags"
SYNAPSE_SIM_PUBLIC = REPO_ROOT / "synapse_sim" / "public"
SYNAPSE_SIM_CONFIG = SYNAPSE_SIM_PUBLIC / "apriltag-config.json"
SYNAPSE_SIM_FIELD = SYNAPSE_SIM_PUBLIC / "field.glb"
DEPLOY_FIELD_MAP = REPO_ROOT / "examples" / "synapseproject" / "deploy" / "fmap.json"

#: The headless-browser test is opt-in because it starts Chrome and loads the
#: full field model. Run it with ``SYNAPSE_TEST_SIM_BROWSER=1``.
RUN_BROWSER_TESTS = os.environ.get("SYNAPSE_TEST_SIM_BROWSER") == "1"


def detectTagIds(frame: np.ndarray):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detector = RobotpyApriltagDetector()
    detector.setFamily("tag36h11")
    return [detection.tagID for detection in detector.detect(gray)]


def fileDigest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quaternionLookDirection(quaternion) -> np.ndarray:
    """Returns the Three.js camera look direction for an [x, y, z, w] quat."""
    x, y, z, w = quaternion
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    return rotation @ np.array([0.0, 0.0, -1.0])


class TestSimCameraPoses(unittest.TestCase):
    def setUp(self):
        self.tableName = f"SynapseTestSimPoses{id(self)}"
        self.tablePatcher = patch.object(NtClient, "NT_TABLE", self.tableName)
        self.tablePatcher.start()
        self.addCleanup(self.tablePatcher.stop)

        self.camera = SimCamera.create(path=0, index=2)

        self.table = (
            NetworkTableInstance.getDefault()
            .getTable(self.tableName)
            .getSubTable(SimCamera.TABLE_NAME)
        )

    def cameraTable(self):
        return self.table.getSubTable(SimCamera.CAMERAS_TABLE).getSubTable("2")

    def test_uses_shared_defaults(self):
        robotPose, cameraPose = self.camera.poses()

        self.assertAlmostEqual(robotPose.translation().x, DEFAULT_ROBOT_POSE[0])
        self.assertAlmostEqual(robotPose.translation().y, DEFAULT_ROBOT_POSE[1])
        self.assertAlmostEqual(cameraPose.translation().z, DEFAULT_CAMERA_OFFSET[2])

    def test_shared_keys_apply_to_every_camera(self):
        self.table.getEntry(SimCamera.ROBOT_POSE_KEY).setDoubleArray([1.0, 2.0, 0.5])
        self.table.getEntry(SimCamera.CAMERA_OFFSET_KEY).setDoubleArray(
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        )

        robotPose, cameraPose = self.camera.poses()

        self.assertAlmostEqual(robotPose.translation().x, 1.0)
        self.assertAlmostEqual(robotPose.translation().y, 2.0)
        self.assertTrue(math.isclose(robotPose.rotation().z, 0.5))
        self.assertAlmostEqual(cameraPose.translation().x, 1.0)
        self.assertAlmostEqual(cameraPose.translation().y, 2.0)
        self.assertAlmostEqual(cameraPose.translation().z, 1.0)
        self.assertTrue(math.isclose(cameraPose.rotation().z, 0.5))

    def test_camera_overrides_take_precedence(self):
        self.table.getEntry(SimCamera.ROBOT_POSE_KEY).setDoubleArray([1.0, 2.0, 0.0])
        self.table.getEntry(SimCamera.CAMERA_OFFSET_KEY).setDoubleArray(
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        )

        cameraTable = self.cameraTable()
        cameraTable.getEntry(SimCamera.ROBOT_POSE_KEY).setDoubleArray([5.0, 6.0, 1.5])
        cameraTable.getEntry(SimCamera.CAMERA_OFFSET_KEY).setDoubleArray(
            [0.0, 0.0, 2.0, 0.0, 0.0, 0.0]
        )

        robotPose, cameraPose = self.camera.poses()

        self.assertAlmostEqual(robotPose.translation().x, 5.0)
        self.assertAlmostEqual(robotPose.translation().y, 6.0)
        self.assertTrue(math.isclose(robotPose.rotation().z, 1.5))
        self.assertAlmostEqual(cameraPose.translation().x, 5.0)
        self.assertAlmostEqual(cameraPose.translation().y, 6.0)
        self.assertAlmostEqual(cameraPose.translation().z, 2.0)
        self.assertTrue(math.isclose(cameraPose.rotation().z, 1.5))

    def test_absolute_camera_pose_overrides_offset(self):
        cameraTable = self.cameraTable()
        cameraTable.getEntry(SimCamera.CAMERA_POSE_KEY).setDoubleArray(
            [3.0, 4.0, 5.0, 0.0, 0.0, 0.25]
        )

        _, cameraPose = self.camera.poses()

        self.assertAlmostEqual(cameraPose.translation().x, 3.0)
        self.assertAlmostEqual(cameraPose.translation().y, 4.0)
        self.assertAlmostEqual(cameraPose.translation().z, 5.0)
        self.assertTrue(math.isclose(cameraPose.rotation().z, 0.25))

    def test_invalid_values_fall_back_and_warn_once(self):
        self.table.getEntry(SimCamera.ROBOT_POSE_KEY).setDoubleArray([1.0])

        with patch("synapse_sim.camera.warn") as warn:
            firstRobotPose, _ = self.camera.poses()
            secondRobotPose, _ = self.camera.poses()

        self.assertAlmostEqual(firstRobotPose.translation().x, DEFAULT_ROBOT_POSE[0])
        self.assertAlmostEqual(secondRobotPose.translation().x, DEFAULT_ROBOT_POSE[0])
        warn.assert_called_once()


class TestSimCameraTransform(unittest.TestCase):
    def test_tag_one_camera_maps_into_the_shared_field_scene(self):
        pose = Pose3d(Translation3d(10.877494, 7.424498, 0.889), Rotation3d())

        position, quaternion = wpi_camera_to_three(pose)

        self.assertAlmostEqual(position[0], L_METERS / 2 - 10.877494)
        self.assertAlmostEqual(position[1], 0.889)
        self.assertAlmostEqual(position[2], 7.424498 - W_METERS / 2)

        # The identity WPI camera looks along +field X, which is -three.x.
        np.testing.assert_allclose(
            quaternionLookDirection(quaternion),
            [-1.0, 0.0, 0.0],
            atol=1e-9,
        )
        np.testing.assert_allclose(
            quaternion, [0.0, math.sqrt(0.5), 0.0, math.sqrt(0.5)]
        )

    def test_yaw_rotation_maps_into_three_coordinates(self):
        pose = Pose3d(
            Translation3d(8.0, 4.0, 0.5),
            Rotation3d(0.0, 0.0, math.pi / 2),
        )

        _, quaternion = wpi_camera_to_three(pose)

        # +90 degree WPI yaw looks along +field Y, which maps to +three.z.
        np.testing.assert_allclose(
            quaternionLookDirection(quaternion),
            [0.0, 0.0, 1.0],
            atol=1e-9,
        )

    def test_spec_uses_the_pipeline_calibration_matrix(self):
        pose = Pose3d(Translation3d(1.0, 2.0, 3.0), Rotation3d())

        spec = camera_spec(4, 640, 480, pose, seq=9)

        self.assertEqual(spec["index"], 4)
        self.assertEqual(spec["width"], 640)
        self.assertEqual(spec["height"], 480)
        self.assertEqual(spec["seq"], 9)
        self.assertEqual(len(spec["position"]), 3)
        self.assertEqual(len(spec["quaternion"]), 4)
        self.assertLess(spec["fovY"], FIELD_OF_VIEW_DEGREES)

        matrix = cameraMatrix(640, 480)
        self.assertAlmostEqual(spec["intrinsics"]["fx"], matrix[0][0])
        self.assertAlmostEqual(spec["intrinsics"]["fy"], matrix[1][1])
        self.assertAlmostEqual(spec["intrinsics"]["cx"], matrix[0][2])
        self.assertAlmostEqual(spec["intrinsics"]["cy"], matrix[1][2])


class TestSimAssets(unittest.TestCase):
    def test_bundled_field_matches_the_shared_viewer(self):
        self.assertTrue((SIM_ASSETS / "viewer.bundle.js").is_file())
        self.assertTrue((SIM_ASSETS / "index.html").is_file())
        self.assertEqual(
            fileDigest(SIM_ASSETS / "field.glb"),
            fileDigest(SYNAPSE_SIM_FIELD),
        )
        self.assertEqual(
            (SIM_ASSETS / "apriltag-config.json").read_bytes(),
            SYNAPSE_SIM_CONFIG.read_bytes(),
        )

    def test_bundled_tags_match_the_shared_viewer(self):
        sourceTags = sorted(SYNAPSE_SIM_PUBLIC.glob("apriltags/*.png"))
        bundledTags = sorted(TAG_ASSETS.glob("*.png"))

        self.assertEqual(
            [path.name for path in bundledTags],
            [path.name for path in sourceTags],
        )
        for source, bundled in zip(sourceTags, bundledTags):
            self.assertEqual(source.read_bytes(), bundled.read_bytes())

    def test_tag_texture_is_one_cell_quieter_than_the_black_square(self):
        image = cv2.imread(
            str(TAG_ASSETS / "tag36_11_00001.png"),
            cv2.IMREAD_UNCHANGED,
        )
        self.assertEqual(image.shape[:2], (10, 10))

        grayscale = image if image.ndim == 2 else image[:, :, 0]
        rows, columns = np.where(grayscale < 128)
        self.assertEqual((columns.min(), columns.max()), (1, 8))
        self.assertEqual((rows.min(), rows.max()), (1, 8))

        # The tag plane in Three.js uses the full 10-cell texture, so it is
        # 10/8 of the physical 6.5 inch black square.
        self.assertAlmostEqual(0.1651 * 10 / 8, 0.206375)

    def test_synapse_sim_config_matches_the_deploy_field_map(self):
        config = json.loads(SYNAPSE_SIM_CONFIG.read_text())
        fieldMap = {
            tag["ID"]: tag["pose"]
            for tag in json.loads(DEPLOY_FIELD_MAP.read_text())["tags"]
        }

        self.assertEqual(len(config["aprilTags"]), 32)
        for tag in config["aprilTags"]:
            x, y, z = tag["position"]
            other = fieldMap[tag["id"]]["translation"]
            self.assertAlmostEqual(L_METERS / 2 - x, other["x"], delta=2e-3)
            self.assertAlmostEqual(W_METERS / 2 - y, other["y"], delta=2e-3)
            self.assertAlmostEqual(z, other["z"], delta=2e-3)


class TestSimulationViewerStore(unittest.TestCase):
    def test_waits_for_the_requested_sequence(self):
        viewer = SimulationViewer()

        seq = viewer.setSpec(0, {"width": 640, "height": 480})

        with self.assertRaises(TimeoutError):
            viewer.waitForFrame(0, seq, timeout=0.01)

        viewer._storeFrame(0, seq, b"frame")
        self.assertEqual(viewer.waitForFrame(0, seq, timeout=0.01), b"frame")

    def test_latest_frame_wins_and_stale_frames_are_ignored(self):
        viewer = SimulationViewer()

        first = viewer.setSpec(0, {"width": 640, "height": 480})
        viewer._storeFrame(0, first, b"first")
        second = viewer.setSpec(0, {"width": 320, "height": 240})

        viewer._storeFrame(0, first, b"out-of-date")
        # A slightly stale frame is preferable to dropping the camera.
        self.assertEqual(viewer.waitForFrame(0, second, timeout=0.01), b"first")

        viewer._storeFrame(0, second, b"second")
        self.assertEqual(viewer.waitForFrame(0, second, timeout=0.01), b"second")

    def test_specs_are_shared_between_cameras(self):
        viewer = SimulationViewer()

        viewer.setSpec(0, {"width": 640, "height": 480})
        viewer.setSpec(1, {"width": 320, "height": 240})
        specs = {spec["index"]: spec for spec in viewer.specs()}

        self.assertEqual(set(specs), {0, 1})
        self.assertEqual(specs[0]["width"], 640)
        self.assertEqual(specs[1]["width"], 320)

        viewer.removeSpec(0)
        self.assertEqual([spec["index"] for spec in viewer.specs()], [1])

    def test_reported_errors_unblock_waiters(self):
        viewer = SimulationViewer()
        seq = viewer.setSpec(0, {"width": 640, "height": 480})
        viewer._onError("browser crashed")

        with self.assertRaisesRegex(RuntimeError, "browser crashed"):
            viewer.waitForFrame(0, seq, timeout=0.01)


@unittest.skipUnless(
    RUN_BROWSER_TESTS,
    "set SYNAPSE_TEST_SIM_BROWSER=1 to run the headless browser test",
)
class TestSimCameraFrame(unittest.TestCase):
    def test_grab_frame_renders_a_detectable_tag(self):
        if findChrome() is None:
            self.skipTest("Chrome or Chromium is not installed")

        tableName = f"SynapseTestSimFrame{id(self)}"

        with patch.object(NtClient, "NT_TABLE", tableName):
            camera = SimCamera.create(path=0, index=0)
            table = (
                NetworkTableInstance.getDefault()
                .getTable(tableName)
                .getSubTable(SimCamera.TABLE_NAME)
            )
            # Tag 1 is at (11.877, 7.424, 0.889) and faces -x, so a camera one
            # metre in front of it looking along +x sees its front face.
            table.getEntry(SimCamera.CAMERA_POSE_KEY).setDoubleArray(
                [10.877494, 7.424498, 0.889, 0.0, 0.0, 0.0]
            )
            camera.setVideoMode(VideoMode(VideoMode.PixelFormat.kMJPEG, 640, 480, 30))

            buffer = np.zeros((480, 640, 3), dtype=np.uint8)
            timestamp, frame = camera.grabFrame(buffer)
            camera.close()

        self.assertGreater(timestamp, 0.0)
        self.assertIs(frame, buffer)
        assert frame is not None
        self.assertIn(1, detectTagIds(frame))


class TestInstallSimulation(unittest.TestCase):
    def setUp(self):
        self.tableName = f"SynapseTestSimSetup{id(self)}"
        self.tablePatcher = patch.object(NtClient, "NT_TABLE", self.tableName)
        self.tablePatcher.start()
        self.addCleanup(self.tablePatcher.stop)

        self.runtimeHandler = MagicMock()
        self.cameraHandler = self.runtimeHandler.cameraHandler
        self.table = (
            NetworkTableInstance.getDefault()
            .getTable(self.tableName)
            .getSubTable(SimCamera.TABLE_NAME)
        )

    def config(self, name="Camera"):
        return CameraConfig(
            name=name,
            id="",
            calibration={},
            defaultPipeline=0,
            streamRes=(320, 240),
        )

    def test_creates_default_camera_when_none_configured(self):
        configs = {}

        with patch.object(GlobalSettings, "getCameraConfigMap", return_value=configs):
            installSimulation(self.runtimeHandler)

        self.cameraHandler.setCameraType.assert_called_once_with(SimCamera)
        self.assertIn(0, configs)
        self.assertEqual(configs[0].id, "sim_camera_0")
        self.assertEqual(
            set(configs[0].calibration),
            {f"{width}x{height}" for width, height in SUPPORTED_RESOLUTIONS},
        )

    def test_installs_every_configured_camera(self):
        configs = {0: self.config("Front"), 1: self.config("Back")}
        configs[1].id = "custom_camera"

        with patch.object(GlobalSettings, "getCameraConfigMap", return_value=configs):
            installSimulation(self.runtimeHandler)

        self.assertEqual(configs[0].id, "sim_camera_0")
        self.assertEqual(configs[1].id, "custom_camera")
        for config in configs.values():
            self.assertIn("1640x1232", config.calibration)

        self.assertEqual(
            list(self.table.getEntry(SimCamera.ROBOT_POSE_KEY).getDoubleArray([])),
            DEFAULT_ROBOT_POSE,
        )
        self.assertEqual(
            list(self.table.getEntry(SimCamera.CAMERA_OFFSET_KEY).getDoubleArray([])),
            DEFAULT_CAMERA_OFFSET,
        )

        camerasTable = self.table.getSubTable(SimCamera.CAMERAS_TABLE)
        for cameraIndex in configs:
            cameraTable = camerasTable.getSubTable(str(cameraIndex))
            for key in (
                SimCamera.ROBOT_POSE_KEY,
                SimCamera.CAMERA_OFFSET_KEY,
                SimCamera.CAMERA_POSE_KEY,
            ):
                self.assertEqual(
                    list(cameraTable.getEntry(key).getDoubleArray([123.0])), []
                )


class TestCameraHandlerSimulation(unittest.TestCase):
    def config(self, name="Camera", cameraID="sim_camera"):
        return CameraConfig(
            name=name,
            id=cameraID,
            calibration={},
            defaultPipeline=0,
            streamRes=(320, 240),
        )

    def test_create_cameras_uses_every_index_for_non_usb_backends(self):
        handler = CameraHandler()
        handler.setCameraType(SimCamera)
        handler.addCamera = MagicMock(return_value=True)
        configs = {0: self.config("Front"), 1: self.config("Back")}

        with patch.object(GlobalSettings, "getCameraConfigMap", return_value=configs):
            handler.createCameras()

        self.assertEqual(
            handler.addCamera.call_args_list,
            [
                call(0, configs[0], 0),
                call(1, configs[1], 1),
            ],
        )

    def test_add_camera_uses_selected_backend(self):
        handler = CameraHandler()
        handler.setCameraType(SimCamera)
        config = self.config()

        with (
            patch("synapse.core.camera_handler.CameraFactory.create") as create,
            patch("synapse.core.camera_handler.CameraHandle"),
            patch.object(handler, "addCameraData"),
        ):
            self.assertTrue(handler.addCamera(3, config, 3))

        create.assert_called_once_with(cameraType=SimCamera, cameraIndex=3, path=3)


if __name__ == "__main__":
    unittest.main()
