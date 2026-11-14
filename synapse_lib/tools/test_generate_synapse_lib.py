# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the SynapseLib source generator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_synapse_lib as generator  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = REPO_ROOT / "synapse_core" / "src" / "synapse"


def test_parse_string_enum(tmp_path: Path) -> None:
    path = tmp_path / "camera.py"
    path.write_text(
        "from enum import Enum\n"
        "\n"
        "class CameraPropKeys(Enum):\n"
        '    kBrightness = "brightness"\n'
        '    kGain = "gain"\n'
    )

    assert generator._parse_string_enum(path, "CameraPropKeys") == [
        ("kBrightness", "brightness"),
        ("kGain", "gain"),
    ]


def test_parse_string_enum_missing_class(tmp_path: Path) -> None:
    path = tmp_path / "camera.py"
    path.write_text("class Other:\n    pass\n")

    with pytest.raises(generator.SchemaError):
        generator._parse_string_enum(path, "CameraPropKeys")


def test_parse_module_strings(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.py"
    path.write_text(
        'DataTableKey = "data"\nResultsTopicKey = "results"\nUnrelated = 3\n'
    )

    assert generator._parse_module_strings(
        path, ("DataTableKey", "ResultsTopicKey")
    ) == {"DataTableKey": "data", "ResultsTopicKey": "results"}


def test_parse_module_strings_missing(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.py"
    path.write_text('DataTableKey = "data"\n')

    with pytest.raises(generator.SchemaError):
        generator._parse_module_strings(path, ("DataTableKey", "ResultsTopicKey"))


def test_discover_pipelines(tmp_path: Path) -> None:
    root = tmp_path / "pipelines"
    nested = root / "custom"
    nested.mkdir(parents=True)
    (nested / "custom_pipeline.py").write_text(
        "from ..core.pipeline import Pipeline, pipelineName\n"
        "\n"
        "class CustomSettings:\n"
        "    pass\n"
        "\n"
        "class CustomResult:\n"
        "    pass\n"
        "\n"
        "@pipelineName('RenamedPipeline')\n"
        "class CustomPipeline(Pipeline[CustomSettings, CustomResult]):\n"
        '    """A custom pipeline."""\n'
        "\n"
        "class ImplicitResult:\n"
        "    pass\n"
        "\n"
        "class ImplicitPipeline(Pipeline[CustomSettings, ImplicitResult]):\n"
        "    pass\n"
        "\n"
        "class NotAPipeline:\n"
        "    pass\n"
    )

    discovered = generator._discover_pipelines(root, {"CustomResult", "ImplicitResult"})

    assert discovered == [
        generator.RuntimePipeline(
            typeString="RenamedPipeline",
            result="CustomResult",
            doc="A custom pipeline.",
        ),
        generator.RuntimePipeline(
            typeString="ImplicitPipeline",
            result="ImplicitResult",
            doc="ImplicitPipeline pipeline.",
        ),
    ]


def test_merge_runtime_schema_preserves_docs_and_warns() -> None:
    raw = {
        "version": 1,
        "tables": {"settings": "settings", "data": "data"},
        "topics": {
            "pipeline": {
                "key": "pipeline",
                "table": "root",
                "doc": "Hand-written pipeline docs.",
            },
            "stale": {"key": "stale", "table": "root", "doc": "Old."},
        },
        "settings": {
            "brightness": {
                "key": "brightness",
                "type": "double",
                "doc": "Hand-written brightness docs.",
            },
            "stale": {"key": "stale", "type": "double", "doc": "Old."},
        },
        "pipelines": {
            "color": {
                "typeString": "ColorPipeline",
                "result": "ColorResult",
                "doc": "Hand-written color docs.",
            },
            "stale": {
                "typeString": "StalePipeline",
                "result": "StaleResult",
                "doc": "Old.",
            },
        },
        "models": [{"name": "ColorResult", "fields": []}],
    }
    runtime = generator.RuntimeApi(
        tables=[("settings", "settings"), ("data", "data")],
        topics=[("pipeline", "root"), ("view_id", "root")],
        settings=[("brightness", "double"), ("contrast", "double")],
        pipelines=[
            generator.RuntimePipeline(
                typeString="ColorPipeline",
                result="ColorResult",
                doc="Runtime color docs.",
            )
        ],
    )

    merged, warnings = generator.merge_runtime_schema(raw, runtime)

    assert merged["topics"]["pipeline"]["doc"] == "Hand-written pipeline docs."
    assert merged["topics"]["view_id"] == {
        "key": "view_id",
        "table": "root",
        "doc": "The camera view ID.",
    }
    assert merged["settings"]["brightness"]["doc"] == "Hand-written brightness docs."
    assert merged["settings"]["contrast"]["type"] == "double"
    assert merged["pipelines"]["color"]["doc"] == "Hand-written color docs."
    assert merged["models"] == raw["models"]
    assert "stale" not in merged["topics"]
    assert "stale" not in merged["settings"]
    assert "stale" not in merged["pipelines"]
    assert len(warnings) == 3
    assert any("topic" in warning for warning in warnings)
    assert any("setting" in warning for warning in warnings)
    assert any("pipeline" in warning for warning in warnings)


@pytest.mark.skipif(not RUNTIME_ROOT.is_dir(), reason="synapse_core is not checked out")
def test_parse_real_runtime_api() -> None:
    api = generator.parse_runtime_api(RUNTIME_ROOT, {"ApriltagResult", "ColorResult"})

    assert ("settings", "settings") in api.tables
    assert ("data", "data") in api.tables
    assert ("pipeline_type", "root") in api.topics
    assert ("results", "data") in api.topics
    assert ("white_balance_temperature", "double") in api.settings
    assert ("orientation", "int") in api.settings

    pipelines = {pipeline.result: pipeline for pipeline in api.pipelines}
    assert pipelines["ApriltagResult"].typeString == "ApriltagPipeline"
    assert pipelines["ColorResult"].typeString == "ColorPipeline"
