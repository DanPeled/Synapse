# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Optional, cast
from unittest.mock import patch

import numpy as np
from synapse.core.settings_api import FileConstraint
from synapse.pipelines.apriltag.apriltag_detector import (
    TAG_BORDER_GREEN,
    TAG_BORDER_RED,
    TAG_ID_BLUE,
    AprilTagDetection,
    AprilTagDetector,
    CameraPoseEstimate,
    drawTagDetectionMarker,
    drawTagDetectionOverlays,
    makeCorners,
    poseCubeObjectPoints,
)
from synapse.pipelines.apriltag.apriltag_napa import NapaApriltagDetector
from synapse.pipelines.apriltag.apriltag_pipeline import (
    DEFAULT_FIELD_MAP_FILE,
    ApriltagPipeline,
    ApriltagPipelineSettings,
    filterTagsByIds,
)
from synapse.pipelines.apriltag.field_loader import ApriltagFieldJson
from typing_extensions import Buffer
from wpimath import Pose3d, Rotation3d, Translation3d

FIELD_JSON = {
    "tags": [
        {
            "ID": 1,
            "pose": {
                "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                "rotation": {"quaternion": {"W": 1.0, "X": 0.0, "Y": 0.0, "Z": 0.0}},
            },
        }
    ],
    "field": {"length": 16.0, "width": 8.0},
}


def _fieldJson(tagId: int, length: float) -> dict:
    return {
        "tags": [
            {
                "ID": tagId,
                "pose": {
                    "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "rotation": {
                        "quaternion": {"W": 1.0, "X": 0.0, "Y": 0.0, "Z": 0.0}
                    },
                },
            }
        ],
        "field": {"length": length, "width": 8.0},
    }


def _detection(tagId: int, left: int, top: int, size: int = 40) -> AprilTagDetection:
    return AprilTagDetection(
        tagID=tagId,
        homography=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        hamming=0,
        corners=makeCorners(
            left, top, left + size, top, left + size, top + size, left, top + size
        ),
        center=(left + size // 2, top + size // 2),
    )


def _hasColor(img: np.ndarray, color: tuple[int, int, int]) -> bool:
    return bool(np.any(np.all(img == np.asarray(color, dtype=np.uint8), axis=2)))


def _countColor(img: np.ndarray, color: tuple[int, int, int]) -> int:
    return int(np.count_nonzero(np.all(img == np.asarray(color, dtype=np.uint8), axis=2)))


def _pipelineWithFieldMap(monkeypatch, root: Path, value: str) -> ApriltagPipeline:
    monkeypatch.setattr("synapse.core.settings_api._getSettingsRoot", lambda: root)
    monkeypatch.setattr(
        "synapse.pipelines.apriltag.apriltag_pipeline._projectRoot", lambda: root
    )

    settings = ApriltagPipelineSettings()
    result = settings.getAPI().setValue("field_map_file", value)
    assert result.isValid, result.errorMessage

    with patch(
        "synapse.pipelines.apriltag.apriltag_pipeline.NapaApriltagDetector"
    ):
        return ApriltagPipeline(settings)


def test_apriltag_settings_expose_field_map_file_setting():
    settings = ApriltagPipelineSettings()
    setting = settings.getAPI().getSetting("field_map_file")

    assert setting is not None
    assert isinstance(setting.constraint, FileConstraint)
    assert setting.defaultValue == DEFAULT_FIELD_MAP_FILE
    assert setting.constraint.fileTypes == {".json"}


def test_pipeline_loads_field_map_from_setting_and_reloads(tmp_path, monkeypatch):
    (tmp_path / "first.json").write_text(json.dumps(_fieldJson(1, 16.0)))
    (tmp_path / "second.json").write_text(json.dumps(_fieldJson(2, 17.0)))

    pipeline = _pipelineWithFieldMap(monkeypatch, tmp_path, "first.json")

    assert pipeline.fmap.getTagPose(1) is not None
    assert pipeline.fmap.getTagPose(2) is None

    pipeline.setSetting(pipeline.settings.field_map_file, "second.json")

    assert pipeline.fmap.getTagPose(2) is not None
    assert pipeline.fmap.getTagPose(1) is None


def test_pipeline_handles_missing_field_map_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synapse.pipelines.apriltag.apriltag_pipeline._projectRoot", lambda: tmp_path
    )

    with patch(
        "synapse.pipelines.apriltag.apriltag_pipeline.NapaApriltagDetector"
    ):
        pipeline = ApriltagPipeline(ApriltagPipelineSettings())

    assert pipeline.fmap.fieldMap == {}


class TestApriltagFieldJson(unittest.TestCase):
    def test_loadFieldCached_reuses_loaded_field(self):
        ApriltagFieldJson.loadFieldCached.cache_clear()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fmap.json"
            path.write_text(json.dumps(FIELD_JSON))

            with patch(
                "synapse.pipelines.apriltag.field_loader.json.load",
                wraps=json.load,
            ) as json_load:
                first = ApriltagFieldJson.loadFieldCached(path)
                second = ApriltagFieldJson.loadFieldCached(path)

        self.assertIs(first, second)
        json_load.assert_called_once()
        tagPose = first.getTagPose(1)
        self.assertIsNotNone(tagPose)
        if tagPose is not None:
            self.assertEqual(tagPose.translation().x, 1.0)


class TestDrawTagDetectionMarker(unittest.TestCase):
    def test_draws_boundary_and_center(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        tag = AprilTagDetection(
            tagID=7,
            homography=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            hamming=0,
            corners=makeCorners(10, 10, 40, 10, 40, 40, 10, 40),
            center=(25, 25),
        )

        drawTagDetectionMarker(tag, img)

        # Boundary is drawn green, center is drawn red.
        self.assertTrue(np.any(img[:, :, 1]))
        self.assertTrue(np.any(img[:, :, 2]))
        self.assertTrue(np.any(img[40, 10:41, 1]))


def test_pose_cube_points_extend_along_tag_normal():
    points = poseCubeObjectPoints(0.2)

    assert points.shape == (8, 3)
    np.testing.assert_allclose(points[:4, 2], 0.0)
    np.testing.assert_allclose(points[4:, 2], 0.2)


def test_draw_tag_detection_overlays_colors_and_projects_cube():
    tagPose = Pose3d(Translation3d(3.0, 0.0, 0.0), Rotation3d(0.0, 0.0, 0.0))
    cameraPose = Pose3d(Translation3d(0.0, 0.0, 0.0), Rotation3d(0.0, 0.0, 0.0))
    cameraMatrix = np.array(
        [[500.0, 0.0, 640.0], [0.0, 500.0, 360.0], [0.0, 0.0, 1.0]]
    )
    cameraPoseEstimate = CameraPoseEstimate(0.0, cameraPose)
    processed = [_detection(1, 200, 100)]
    rejected = [_detection(2, 400, 100)]

    def getTagPose(tagId: int) -> Optional[Pose3d]:
        return tagPose if tagId == 1 else None

    withoutCube = np.zeros((720, 1280, 3), dtype=np.uint8)
    withCube = np.zeros((720, 1280, 3), dtype=np.uint8)

    drawTagDetectionOverlays(
        withoutCube,
        processed + rejected,
        processed,
        getTagPose,
        None,
        0.2,
        cameraMatrix,
        np.zeros(5),
    )
    drawTagDetectionOverlays(
        withCube,
        processed + rejected,
        processed,
        getTagPose,
        cameraPoseEstimate.cameraPoseEstimate,
        0.2,
        cameraMatrix,
        np.zeros(5),
    )

    assert _hasColor(withCube, TAG_BORDER_RED)
    assert _hasColor(withCube, TAG_BORDER_GREEN)
    assert _hasColor(withCube, TAG_ID_BLUE)
    assert _countColor(withCube, TAG_BORDER_GREEN) > _countColor(
        withoutCube, TAG_BORDER_GREEN
    )


def test_pipeline_draws_rejected_and_unusable_tags_in_red(tmp_path, monkeypatch):
    (tmp_path / "field.json").write_text(json.dumps(_fieldJson(1, 16.0)))
    pipeline = _pipelineWithFieldMap(monkeypatch, tmp_path, "field.json")
    pipeline.setSetting("tag_filter", [1, 3])

    detections = [
        _detection(1, 100, 100),
        _detection(2, 200, 100),
        _detection(3, 300, 100),
    ]
    cameraPose = Pose3d(Translation3d(0.0, 0.0, 0.0), Rotation3d(0.0, 0.0, 0.0))
    img = np.zeros((720, 1280, 3), dtype=np.uint8)

    with (
        patch.object(pipeline.apriltagDetector, "detect", return_value=detections),
        patch.object(
            pipeline.poseEstimator,
            "estimate",
            return_value=CameraPoseEstimate(0.0, cameraPose),
        ),
        patch.object(pipeline, "setDataValue"),
        patch.object(pipeline, "setResults"),
    ):
        assert pipeline.processFrame(img, 0.0) is img

    assert tuple(img[100, 100]) == TAG_BORDER_GREEN
    assert tuple(img[100, 200]) == TAG_BORDER_RED
    assert tuple(img[100, 300]) == TAG_BORDER_RED
    assert _hasColor(img, TAG_ID_BLUE)


class _FakeNapaDetector:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        _FakeNapaDetector.instances.append(self)

    def detect(self, image):
        return [
            types.SimpleNamespace(
                tag_id=7,
                corners=np.array(
                    [[10.0, 20.0], [30.0, 40.0], [50.0, 60.0], [70.0, 80.0]]
                ),
                hamming=1,
                center=np.array([1.4, 2.6]),
                homography=np.array(
                    [[10.0, 0.0, 1.4], [0.0, 10.0, 2.6], [0.0, 0.0, 1.0]]
                ),
            )
        ]

    def close(self):
        self.closed = True


class TestNapaApriltagDetector(unittest.TestCase):
    def setUp(self):
        _FakeNapaDetector.instances.clear()
        module = types.ModuleType("napa_vision")
        setattr(module, "NapaDetector", _FakeNapaDetector)
        self.patcher = patch.dict(sys.modules, {"napa_vision": module})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_detects_and_converts_napa_results(self):
        detector = NapaApriltagDetector()

        frame = cast(Buffer, np.zeros((100, 100), dtype=np.uint8))

        detections = detector.detect(frame)

        self.assertEqual(len(detections), 1)
        detection = detections[0]
        self.assertEqual(detection.tagID, 7)
        self.assertEqual(detection.hamming, 1)
        self.assertEqual(detection.center, (1, 3))
        self.assertEqual(
            detection.corners,
            makeCorners(30, 40, 10, 20, 70, 80, 50, 60),
        )
        self.assertEqual(
            detection.homography,
            (10.0, 0.0, 1.4, 0.0, 10.0, 2.6, 0.0, 0.0, 1.0),
        )

        kwargs = _FakeNapaDetector.instances[0].kwargs
        self.assertEqual(kwargs["family"], "tag36h11")
        self.assertEqual(kwargs["min_tag_px"], 32)
        self.assertIsNone(kwargs["max_hamming"])

    def test_setConfig_rebuilds_detector_with_napa_settings(self):
        detector = NapaApriltagDetector()
        oldDetector = _FakeNapaDetector.instances[0]

        detector.setConfig(
            AprilTagDetector.Config(
                minTagPx=16,
                maxHamming=2,
                minContrast=30,
                minBorderCells=10,
                sharpening=0.5,
                maxDetections=12,
            )
        )

        self.assertTrue(oldDetector.closed)
        kwargs = _FakeNapaDetector.instances[-1].kwargs
        self.assertEqual(kwargs["min_tag_px"], 16)
        self.assertEqual(kwargs["max_hamming"], 2)
        self.assertEqual(kwargs["min_contrast"], 30)
        self.assertEqual(kwargs["min_border_cells"], 10)
        self.assertEqual(kwargs["sharpening"], 0.5)
        self.assertEqual(kwargs["max_detections"], 12)

    def test_setFamily_rebuilds_detector(self):
        detector = NapaApriltagDetector()
        oldDetector = _FakeNapaDetector.instances[0]

        detector.setFamily("tag16h5")

        self.assertTrue(oldDetector.closed)
        self.assertEqual(_FakeNapaDetector.instances[-1].kwargs["family"], "tag16h5")


class TestFilterTagsByIds(unittest.TestCase):
    @staticmethod
    def makeDetection(tagID: int) -> AprilTagDetection:
        return AprilTagDetection(
            tagID=tagID,
            homography=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            hamming=0,
            corners=makeCorners(0, 0, 1, 0, 1, 1, 0, 1),
            center=(0, 0),
        )

    def test_empty_filter_accepts_every_tag(self):
        tags = [self.makeDetection(1), self.makeDetection(2)]

        self.assertEqual(filterTagsByIds(tags, []), tags)
        self.assertEqual(filterTagsByIds(tags, None), tags)

    def test_filter_keeps_only_requested_ids(self):
        tags = [
            self.makeDetection(1),
            self.makeDetection(2),
            self.makeDetection(3),
        ]

        filtered = filterTagsByIds(tags, [2, 3])

        self.assertEqual([tag.tagID for tag in filtered], [2, 3])

    def test_filter_accepts_precomputed_set(self):
        tags = [
            self.makeDetection(1),
            self.makeDetection(2),
            self.makeDetection(3),
        ]

        filtered = filterTagsByIds(tags, frozenset({1, 3}))

        self.assertEqual([tag.tagID for tag in filtered], [1, 3])

    def test_filter_with_no_matches_returns_empty_list(self):
        tags = [self.makeDetection(1)]

        self.assertEqual(filterTagsByIds(tags, [7]), [])


if __name__ == "__main__":
    unittest.main()
