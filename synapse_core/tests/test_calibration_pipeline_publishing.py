# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, call

from synapse.pipelines.system.calibration_pipeline import CalibrationPipeline


def makePipeline() -> CalibrationPipeline:
    # Avoid constructing cv2 detector state; these helpers only need the cache
    # fields and ``setDataValue``.
    pipeline = object.__new__(CalibrationPipeline)
    pipeline._lastPicturesLeft = None
    pipeline._lastCanTakePicture = None
    pipeline.setDataValue = MagicMock()
    return pipeline


def test_pictures_left_is_published_only_on_change() -> None:
    pipeline = makePipeline()

    pipeline._publishPicturesLeft("3 / 20")
    pipeline._publishPicturesLeft("3 / 20")
    pipeline._publishPicturesLeft("2 / 20")

    assert pipeline.setDataValue.call_args_list == [
        call("Pictures Left", "3 / 20"),
        call("Pictures Left", "2 / 20"),
    ]


def test_can_take_picture_is_published_only_on_change() -> None:
    pipeline = makePipeline()

    pipeline._publishCanTakePicture(False)
    pipeline._publishCanTakePicture(False)
    pipeline._publishCanTakePicture(True)
    pipeline._publishCanTakePicture(True)

    assert pipeline.setDataValue.call_args_list == [
        call("Can Take Picture", False),
        call("Can Take Picture", True),
    ]
