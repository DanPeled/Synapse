# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the cached result deserialization metadata."""

from dataclasses import dataclass, field
from typing import List, Optional

from wpimath import Pose3d

from synapselib._deserialization import from_dict
from synapselib.pipelines.apriltag import ApriltagDetection, ApriltagResult


@dataclass
class _Defaults:
    values: List[int] = field(default_factory=list)
    label: str = "default"
    ratio: Optional[float] = None


@dataclass
class _ExplicitNull:
    pose: Pose3d


def test_cached_metadata_reuses_converters_between_calls():
    payload = {
        "tags": [
            {"tag_id": 3, "hamming": 0, "tagPose_screenSpace": [10, 20]},
        ],
        "cameraEstimate_fieldSpace": None,
        "reprojection_error": 1.25,
    }

    first = from_dict(ApriltagResult, payload)
    second = from_dict(ApriltagResult, payload)

    assert first == second
    assert isinstance(first.tags[0], ApriltagDetection)
    assert first.tags[0].tag_id == 3
    assert first.cameraEstimate_fieldSpace is None


def test_default_factories_are_not_shared_between_results():
    first = from_dict(_Defaults, {"ratio": 2})
    second = from_dict(_Defaults, {})

    assert first.values == []
    assert first.label == "default"
    # MessagePack integers may arrive where a float is declared.
    assert first.ratio == 2.0
    assert isinstance(first.ratio, float)

    first.values.append(7)
    assert second.values == []


def test_explicit_null_keeps_the_legacy_behavior():
    # The original converter returned None before inspecting the annotation.
    result = from_dict(_ExplicitNull, {"pose": None})
    assert result.pose is None


def test_unknown_keys_are_ignored_with_cached_fields():
    result = from_dict(
        _Defaults,
        {"unknown": "ignored", "label": "known", "values": [1, 2, 3]},
    )

    assert result.label == "known"
    assert result.values == [1, 2, 3]
    assert result.ratio is None
