#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Generate SynapseLib source files from the runtime API and shared schema.

NetworkTables paths, camera settings, and pipeline type strings are read from
the ``synapse_core`` source tree with :mod:`ast`, so changing the runtime
constants and rerunning this script updates the schema and both clients.

Result models are language-neutral declarations in
``schema/synapse_lib.json``. They stay hand-maintained because the runtime's
wire shape is not always the same as its internal dataclasses (AprilTags map
through ``ApriltagsJson.toDict``).

Usage::

    python tools/generate_synapse_lib.py            # sync runtime -> schema -> clients
    python tools/generate_synapse_lib.py --check    # fail if anything is stale

Custom pipelines do not need to be part of this schema. Users can define their
own result classes exactly like the generated ones and pass them to
``SynapsePipelineType`` / ``SynapseCamera``.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class SchemaError(ValueError):
    """Raised when the schema is malformed or internally inconsistent."""


@dataclass(frozen=True)
class TypeSpec:
    """A parsed schema type."""

    kind: str
    inner: Optional["TypeSpec"] = None
    name: Optional[str] = None


PRIMITIVES = {"int", "double", "bool", "string"}

PYTHON_TYPES = {"int": "int", "double": "float", "bool": "bool", "string": "str"}

JAVA_TYPES = {"int": "int", "double": "double", "bool": "boolean", "string": "String"}

JAVA_BOXED_TYPES = {
    "int": "Integer",
    "double": "Double",
    "bool": "Boolean",
    "string": "String",
}

PIPELINE_CLASS_DOC = """Represents a Synapse pipeline. Each pipeline is associated with a result
 * class that defines the type of data returned."""


def parse_type(raw: str) -> TypeSpec:
    """Parse a type expression such as ``optional<list<double>>``."""
    raw = raw.strip()
    if raw in PRIMITIVES:
        return TypeSpec(raw)
    if raw.startswith("list<") and raw.endswith(">"):
        return TypeSpec("list", parse_type(raw[len("list<") : -1]))
    if raw.startswith("optional<") and raw.endswith(">"):
        return TypeSpec("optional", parse_type(raw[len("optional<") : -1]))
    if raw.startswith("record:"):
        name = raw[len("record:") :]
        if not name:
            raise SchemaError("Empty record reference")
        return TypeSpec("record", name=name)
    raise SchemaError(f"Unsupported type expression: {raw!r}")


def python_type(spec: TypeSpec) -> str:
    if spec.kind in PYTHON_TYPES:
        return PYTHON_TYPES[spec.kind]
    if spec.kind == "list":
        assert spec.inner is not None
        return f"List[{python_type(spec.inner)}]"
    if spec.kind == "optional":
        assert spec.inner is not None
        return f"Optional[{python_type(spec.inner)}]"
    if spec.kind == "record":
        assert spec.name is not None
        return spec.name
    raise AssertionError(spec)


def java_type(spec: TypeSpec, boxed: bool = False) -> str:
    if spec.kind in JAVA_TYPES:
        return JAVA_BOXED_TYPES[spec.kind] if boxed else JAVA_TYPES[spec.kind]
    if spec.kind == "list":
        assert spec.inner is not None
        return f"{java_type(spec.inner)}[]"
    if spec.kind == "optional":
        assert spec.inner is not None
        return java_type(spec.inner, boxed=True)
    if spec.kind == "record":
        assert spec.name is not None
        return spec.name
    raise AssertionError(spec)


def is_array(spec: TypeSpec) -> bool:
    return spec.kind == "list" or (
        spec.kind == "optional" and spec.inner is not None and spec.inner.kind == "list"
    )


def is_reference(spec: TypeSpec) -> bool:
    return (
        spec.kind in {"string", "record"}
        or spec.kind == "optional"
        or spec.kind == "list"
    )


def require_mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> List[Any]:
    if not isinstance(value, list):
        raise SchemaError(f"{label} must be a list")
    return value


# ---------------------------------------------------------------------------
# Helper snippets
#
# Helpers are referenced by name from the schema. Keeping the snippets here
# means the schema stays language-neutral while generated classes can still
# expose the small convenience methods that users expect.
# ---------------------------------------------------------------------------

PYTHON_HELPERS: Dict[str, Dict[str, Any]] = {
    "apriltagScreenX": {
        "imports": set(),
        "code": """    @property
    def tx(self) -> float:
        \"\"\"Returns the tag's horizontal position in screen space.\"\"\"
        return self.tagPose_screenSpace[0]
""",
    },
    "apriltagScreenY": {
        "imports": set(),
        "code": """    @property
    def ty(self) -> float:
        \"\"\"Returns the tag's vertical position in screen space.\"\"\"
        return self.tagPose_screenSpace[1]
""",
    },
    "apriltagCameraPose3d": {
        "imports": {"math", "geometry"},
        "code": """    @property
    def cameraEstimate_fieldSpace3d(self) -> Optional[Pose3d]:
        \"\"\"Returns the camera's estimated pose in field space as a 3D pose.\"\"\"
        estimate = self.cameraEstimate_fieldSpace
        if estimate is None:
            return None
        if len(estimate) < 6:
            raise ValueError(
                \"cameraEstimate_fieldSpace must contain [x, y, z, roll, pitch, yaw]\"
            )
        return Pose3d(
            translation=Translation3d(estimate[0], estimate[1], estimate[2]),
            # The runtime serializes roll/pitch/yaw in degrees, but the
            # Rotation3d constructor expects radians.
            rotation=Rotation3d(
                math.radians(estimate[3]),
                math.radians(estimate[4]),
                math.radians(estimate[5]),
            ),
        )
""",
    },
}

JAVA_HELPERS: Dict[str, Dict[str, Any]] = {
    "apriltagScreenX": {
        "imports": set(),
        "code": """  /**
   * Returns the tag's horizontal position in screen space.
   *
   * @return the tag's horizontal screen-space position
   */
  public double tx() {
    return tagPose_screenSpace[0];
  }

""",
    },
    "apriltagScreenY": {
        "imports": set(),
        "code": """  /**
   * Returns the tag's vertical position in screen space.
   *
   * @return the tag's vertical screen-space position
   */
  public double ty() {
    return tagPose_screenSpace[1];
  }

""",
    },
    "apriltagCameraPose3d": {
        "imports": {
            "edu.wpi.first.math.geometry.Pose3d",
            "edu.wpi.first.math.geometry.Rotation3d",
            "edu.wpi.first.math.geometry.Translation3d",
        },
        "code": """  /**
   * Returns the camera's estimated pose in field space as a 3D pose.
   *
   * @return the estimated field-space pose, or {@code null} when no estimate was published
   */
  public Pose3d cameraEstimate_fieldSpace3d() {
    if (cameraEstimate_fieldSpace == null || cameraEstimate_fieldSpace.length < 6) {
      return null;
    }
    return new Pose3d(
        new Translation3d(
            cameraEstimate_fieldSpace[0],
            cameraEstimate_fieldSpace[1],
            cameraEstimate_fieldSpace[2]),
        new Rotation3d(
            Math.toRadians(cameraEstimate_fieldSpace[3]),
            Math.toRadians(cameraEstimate_fieldSpace[4]),
            Math.toRadians(cameraEstimate_fieldSpace[5])));
  }

""",
    },
}


# ---------------------------------------------------------------------------
# Schema loading and validation
# ---------------------------------------------------------------------------


class Schema:
    """Validated view of the raw schema."""

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.raw = raw
        self.tables = require_mapping(raw.get("tables", {}), "tables")
        self.topics = require_mapping(raw.get("topics", {}), "topics")
        self.settings = require_mapping(raw.get("settings", {}), "settings")
        self.pipelines = require_mapping(raw.get("pipelines", {}), "pipelines")

        models: List[Dict[str, Any]] = []
        for index, model in enumerate(require_list(raw.get("models", []), "models")):
            model = dict(require_mapping(model, f"models[{index}]"))
            model["fields"] = [
                dict(require_mapping(field, f"models[{index}].fields[{field_index}]"))
                for field_index, field in enumerate(
                    require_list(model.get("fields", []), f"models[{index}].fields")
                )
            ]
            models.append(model)
        self.models = models
        self.modelsByName = {model["name"]: model for model in self.models}
        self._validate()

    def _validate(self) -> None:
        if len(self.modelsByName) != len(self.models):
            raise SchemaError("Model names must be unique")

        for modelName, model in self.modelsByName.items():
            self._require_text(modelName, model, "name")
            self._require_text(modelName, model, "pythonModule")
            self._require_text(modelName, model, "javaPackage")
            pythonNames = set()
            javaNames = set()
            for field in model["fields"]:
                self._require_text(modelName, field, "name")
                self._require_text(modelName, field, "type")
                spec = parse_type(field["type"])
                if spec.kind == "record" and spec.name not in self.modelsByName:
                    raise SchemaError(
                        f"{modelName}.{field['name']} references unknown model {spec.name}"
                    )
                pythonName = field["name"]
                javaName = field.get("javaName", field["name"])
                if pythonName in pythonNames:
                    raise SchemaError(
                        f"Duplicate Python field {modelName}.{pythonName}"
                    )
                if javaName in javaNames:
                    raise SchemaError(f"Duplicate Java field {modelName}.{javaName}")
                pythonNames.add(pythonName)
                javaNames.add(javaName)
                for helper in field.get("helpers", []):
                    raise SchemaError("Helpers belong on the model, not a field")
            for helper in model.get("helpers", []):
                if helper not in PYTHON_HELPERS or helper not in JAVA_HELPERS:
                    raise SchemaError(f"Unknown helper {helper!r} on {modelName}")

        for pipelineName, pipeline in self.pipelines.items():
            pipeline = require_mapping(pipeline, f"pipelines.{pipelineName}")
            self._require_text(pipelineName, pipeline, "typeString")
            result = pipeline.get("result")
            if result not in self.modelsByName:
                raise SchemaError(
                    f"Pipeline {pipelineName} references unknown result {result!r}"
                )

        for topicName, topic in self.topics.items():
            topic = require_mapping(topic, f"topics.{topicName}")
            self._require_text(topicName, topic, "key")
            table = topic.get("table", "root")
            if table != "root" and table not in self.tables:
                raise SchemaError(
                    f"Topic {topicName} references unknown table {table!r}"
                )

        for settingName, setting in self.settings.items():
            setting = require_mapping(setting, f"settings.{settingName}")
            self._require_text(settingName, setting, "key")
            self._require_text(settingName, setting, "type")
            if setting["type"] not in PRIMITIVES:
                raise SchemaError(
                    f"Setting {settingName} has unsupported type {setting['type']!r}"
                )

    @staticmethod
    def _require_text(label: str, value: Dict[str, Any], key: str) -> None:
        if not isinstance(value.get(key), str) or not value[key]:
            raise SchemaError(f"{label}.{key} must be a non-empty string")


# ---------------------------------------------------------------------------
# Runtime source extraction
#
# The runtime is the source of truth for NetworkTables keys and pipeline type
# strings. Parsing the source with AST avoids importing synapse_core, which
# pulls in OpenCV, Numba, and other heavy optional dependencies.
# ---------------------------------------------------------------------------


SCHEMA_COMMENT = (
    "The topics, settings, and pipelines sections are generated from the "
    "synapse_core runtime source. The models section is maintained by hand. "
    "Run `python tools/generate_synapse_lib.py` after changing either."
)

DEFAULT_TOPIC_DOCS = {
    "view_id": "The camera view ID.",
    "pipeline": "The selected pipeline index.",
    "record": "The camera recording state.",
    "pipeline_type": "The selected pipeline's type string.",
    "results": "The latest pipeline results, serialized with MessagePack.",
    "captureLatency": "The latest capture latency, in seconds.",
    "processLatency": "The latest processing latency, in seconds.",
}

# Runtime camera properties are numeric, but the client needs to know whether
# to expose them as integers or doubles. Known keys keep the type from the
# committed schema; new keys default to double unless listed here.
DEFAULT_SETTING_TYPES = {"orientation": "int"}


@dataclass(frozen=True)
class RuntimePipeline:
    """A pipeline discovered in the runtime source."""

    typeString: str
    result: str
    doc: str


@dataclass(frozen=True)
class RuntimeApi:
    """The parts of the runtime API that the clients expose."""

    tables: List[Tuple[str, str]]
    topics: List[Tuple[str, str]]
    settings: List[Tuple[str, str]]
    pipelines: List[RuntimePipeline]


def _parse_python(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except OSError as error:
        raise SchemaError(f"Could not read {path}: {error}") from error
    except SyntaxError as error:
        raise SchemaError(f"Could not parse {path}: {error}") from error


def _parse_string_enum(path: Path, className: str) -> List[Tuple[str, str]]:
    """Return ``(member, value)`` pairs for a string-valued Enum class."""
    tree = _parse_python(path)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != className:
            continue
        members: List[Tuple[str, str]] = []
        for statement in node.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            value = statement.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                members.append((target.id, value.value))
        if not members:
            raise SchemaError(f"{className} in {path} has no string members")
        return members
    raise SchemaError(f"Could not find {className} in {path}")


def _parse_module_strings(path: Path, names: Sequence[str]) -> Dict[str, str]:
    """Return module-level string constants with the requested names."""
    wanted = set(names)
    found: Dict[str, str] = {}
    for node in _parse_python(path).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if (
            isinstance(target, ast.Name)
            and target.id in wanted
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            found[target.id] = value.value
    missing = wanted - found.keys()
    if missing:
        raise SchemaError(f"Could not find {', '.join(sorted(missing))} in {path}")
    return found


def _node_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _pipeline_result_name(node: ast.ClassDef) -> Optional[str]:
    for base in node.bases:
        if not isinstance(base, ast.Subscript) or _node_name(base.value) != "Pipeline":
            continue
        slice_node = base.slice
        if isinstance(slice_node, ast.Tuple) and len(slice_node.elts) == 2:
            return _node_name(slice_node.elts[1])
    return None


def _pipeline_type_name(node: ast.ClassDef) -> Optional[str]:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if _node_name(decorator.func) != "pipelineName" or not decorator.args:
            continue
        argument = decorator.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            return argument.value
    return None


def _first_doc_line(node: ast.ClassDef) -> Optional[str]:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def _discover_pipelines(pipelinesRoot: Path, modelNames: set) -> List[RuntimePipeline]:
    """Find runtime pipelines whose result type is a client model."""
    discovered: List[RuntimePipeline] = []
    seenResults = set()
    for path in sorted(pipelinesRoot.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        for node in _parse_python(path).body:
            if not isinstance(node, ast.ClassDef):
                continue
            result = _pipeline_result_name(node)
            if result is None or result not in modelNames or result in seenResults:
                continue
            seenResults.add(result)
            typeString = _pipeline_type_name(node) or node.name
            discovered.append(
                RuntimePipeline(
                    typeString=typeString,
                    result=result,
                    doc=_first_doc_line(node) or f"{typeString} pipeline.",
                )
            )
    return discovered


def parse_runtime_api(runtimeRoot: Path, modelNames: set) -> RuntimeApi:
    """Extract client-visible API values from the runtime source tree."""
    if not runtimeRoot.is_dir():
        raise SchemaError(f"Runtime source directory not found: {runtimeRoot}")

    coreRoot = runtimeRoot / "core"
    cameraFactory = coreRoot / "camera_factory.py"
    ntKeys = coreRoot / "nt_keys.py"
    pipelineSource = coreRoot / "pipeline.py"

    cameraProperties = _parse_string_enum(cameraFactory, "CameraPropKeys")
    cameraSettings = _parse_string_enum(cameraFactory, "CameraSettingsKeys")
    ntMembers = dict(_parse_string_enum(ntKeys, "NTKeys"))
    pipelineConstants = _parse_module_strings(
        pipelineSource, ("DataTableKey", "ResultsTopicKey")
    )

    tables = [
        ("settings", ntMembers["kSettings"]),
        ("data", pipelineConstants["DataTableKey"]),
    ]

    topics: List[Tuple[str, str]] = [(value, "root") for _, value in cameraSettings]
    topics.append((pipelineConstants["ResultsTopicKey"], "data"))
    for member in ("kProcessLatency", "kCaptureLatency"):
        topics.append((ntMembers[member], "root"))

    settings: List[Tuple[str, str]] = [
        (value, DEFAULT_SETTING_TYPES.get(value, "double"))
        for _, value in cameraProperties
    ]

    return RuntimeApi(
        tables=tables,
        topics=topics,
        settings=settings,
        pipelines=_discover_pipelines(runtimeRoot / "pipelines", modelNames),
    )


def _default_topic_doc(key: str) -> str:
    return DEFAULT_TOPIC_DOCS.get(
        key, f"The {key.replace('_', ' ')} NetworkTables entry."
    )


def _default_setting_doc(key: str) -> str:
    return f"Camera {key.replace('_', ' ')}."


def _warn_dropped(
    section: str,
    old: Dict[str, Any],
    derivedKeys: set,
    warnings: List[str],
) -> None:
    for name, entry in old.items():
        if not isinstance(entry, dict):
            continue
        key = entry.get("key") if section != "pipelines" else entry.get("result")
        if isinstance(key, str) and key not in derivedKeys:
            warnings.append(
                f"Dropped {section} {name!r}: {key!r} is not present in the runtime source"
            )


def _merge_topics(
    old: Dict[str, Any],
    derived: List[Tuple[str, str]],
    warnings: List[str],
) -> Dict[str, Any]:
    derivedByKey: Dict[str, str] = {}
    for key, table in derived:
        derivedByKey.setdefault(key, table)

    merged: Dict[str, Any] = {}
    consumed = set()
    # Preserve the existing order and documentation for keys that still exist.
    for name, entry in old.items():
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key not in derivedByKey or key in consumed:
            continue
        merged[name] = {
            "key": key,
            "table": derivedByKey[key],
            "doc": entry.get("doc") or _default_topic_doc(key),
        }
        consumed.add(key)
    for key, table in derived:
        if key in consumed:
            continue
        merged[key] = {
            "key": key,
            "table": table,
            "doc": _default_topic_doc(key),
        }
        consumed.add(key)

    _warn_dropped("topic", old, set(derivedByKey), warnings)
    return merged


def _merge_settings(
    old: Dict[str, Any],
    derived: List[Tuple[str, str]],
    warnings: List[str],
) -> Dict[str, Any]:
    derivedByKey: Dict[str, str] = {}
    for key, settingType in derived:
        derivedByKey.setdefault(key, settingType)

    merged: Dict[str, Any] = {}
    consumed = set()
    for name, entry in old.items():
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key not in derivedByKey or key in consumed:
            continue
        merged[name] = {
            "key": key,
            "type": entry.get("type") or derivedByKey[key],
            "doc": entry.get("doc") or _default_setting_doc(key),
        }
        consumed.add(key)
    for key, settingType in derived:
        if key in consumed:
            continue
        merged[key] = {
            "key": key,
            "type": settingType,
            "doc": _default_setting_doc(key),
        }
        consumed.add(key)

    _warn_dropped("setting", old, set(derivedByKey), warnings)
    return merged


def _pipeline_entry_name(result: str, typeString: str) -> str:
    if result.endswith("Result"):
        base = result[: -len("Result")]
    elif typeString.endswith("Pipeline"):
        base = typeString[: -len("Pipeline")]
    else:
        base = typeString
    return base[:1].lower() + base[1:]


def _merge_pipelines(
    old: Dict[str, Any],
    derived: List[RuntimePipeline],
    warnings: List[str],
) -> Dict[str, Any]:
    derivedByResult: Dict[str, RuntimePipeline] = {}
    for pipeline in derived:
        derivedByResult.setdefault(pipeline.result, pipeline)

    merged: Dict[str, Any] = {}
    consumed = set()
    for name, entry in old.items():
        if not isinstance(entry, dict):
            continue
        result = entry.get("result")
        if result not in derivedByResult or result in consumed:
            continue
        pipeline = derivedByResult[result]
        merged[name] = {
            "typeString": pipeline.typeString,
            "result": pipeline.result,
            "doc": entry.get("doc") or pipeline.doc,
        }
        consumed.add(result)
    for pipeline in derived:
        if pipeline.result in consumed:
            continue
        merged[_pipeline_entry_name(pipeline.result, pipeline.typeString)] = {
            "typeString": pipeline.typeString,
            "result": pipeline.result,
            "doc": pipeline.doc,
        }
        consumed.add(pipeline.result)

    derivedResults = {pipeline.result for pipeline in derived}
    for name, entry in old.items():
        if not isinstance(entry, dict):
            continue
        result = entry.get("result")
        if isinstance(result, str) and result not in derivedResults:
            warnings.append(
                f"Dropped pipeline {name!r}: {result!r} has no runtime pipeline"
            )
    return merged


def merge_runtime_schema(
    raw: Dict[str, Any],
    runtime: RuntimeApi,
) -> Tuple[Dict[str, Any], List[str]]:
    """Merge runtime-derived API values into the committed schema."""
    warnings: List[str] = []

    merged: Dict[str, Any] = {
        "$comment": SCHEMA_COMMENT,
        "version": raw.get("version", 1),
        "tables": {name: key for name, key in runtime.tables},
        "topics": _merge_topics(
            require_mapping(raw.get("topics", {}), "topics"),
            runtime.topics,
            warnings,
        ),
        "settings": _merge_settings(
            require_mapping(raw.get("settings", {}), "settings"),
            runtime.settings,
            warnings,
        ),
        "pipelines": _merge_pipelines(
            require_mapping(raw.get("pipelines", {}), "pipelines"),
            runtime.pipelines,
            warnings,
        ),
        "models": raw.get("models", []),
    }
    for key, value in raw.items():
        if key not in merged:
            merged[key] = value

    return merged, warnings


def render_schema(schema: Dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Python generation
# ---------------------------------------------------------------------------


PYTHON_HEADER = """# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Generated from schema/synapse_lib.json. Do not edit by hand.
# Run `python tools/generate_synapse_lib.py` to regenerate.
"""


def python_field_annotation(field: Dict[str, Any]) -> str:
    return python_type(parse_type(field["type"]))


def render_python_module(schema: Schema, models: Sequence[Dict[str, Any]]) -> str:
    """Render one Python module containing all models for that module."""
    typingImports = {"Any"}
    geometryNeeded = False
    mathNeeded = False
    for model in models:
        for field in model["fields"]:
            _collect_python_typing(parse_type(field["type"]), typingImports)
        for helper in model.get("helpers", []):
            imports = PYTHON_HELPERS[helper]["imports"]
            geometryNeeded = geometryNeeded or "geometry" in imports
            mathNeeded = mathNeeded or "math" in imports

    lines: List[str] = [PYTHON_HEADER, "\nfrom __future__ import annotations\n\n"]
    if mathNeeded:
        lines.append("import math\n")
    lines.append("from dataclasses import dataclass\n")
    lines.append(f"from typing import {', '.join(sorted(typingImports))}\n")
    crossModuleImports: List[str] = []
    localNames = {model["name"] for model in models}
    importedNames: set = set()
    for model in models:
        for field in model["fields"]:
            for ref in _record_refs(parse_type(field["type"])):
                if ref.name in localNames or ref.name in importedNames:
                    continue
                other = schema.modelsByName[ref.name]
                crossModuleImports.append(
                    f"from {other['pythonModule']} import {ref.name}\n"
                )
                importedNames.add(ref.name)
    if geometryNeeded or crossModuleImports:
        lines.append("\n")
        if geometryNeeded:
            lines.append(
                "from wpimath.geometry import Pose3d, Rotation3d, Translation3d\n"
            )
        lines.extend(crossModuleImports)

    lines.append("\n\ndef _hashable(value: Any) -> Any:\n")
    lines.append("    if isinstance(value, (list, tuple)):\n")
    lines.append("        return tuple(_hashable(item) for item in value)\n")
    lines.append("    if isinstance(value, dict):\n")
    lines.append(
        "        return tuple(sorted((_hashable(k), _hashable(v)) for k, v in value.items()))\n"
    )
    lines.append("    return value\n")

    for model in models:
        lines.extend(_render_python_class(model))
    return "".join(lines)


def _render_python_class(model: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["\n\n@dataclass(frozen=True)\n"]
    lines.append(f"class {model['name']}:\n")
    doc = model.get("doc", "")
    if doc:
        lines.append(f'    """{doc}"""\n')
    else:
        lines.append('    """"""\n')
    if not model["fields"]:
        lines.append("    pass\n")
    for field in model["fields"]:
        lines.append("\n")
        lines.append(f"    {field['name']}: {python_field_annotation(field)}\n")
        if field.get("doc"):
            lines.append(f'    """{field["doc"]}"""\n')

    lines.append("\n    def __hash__(self) -> int:\n")
    if model["fields"]:
        parts = []
        for field in model["fields"]:
            if is_array(parse_type(field["type"])):
                parts.append(f"_hashable(self.{field['name']})")
            else:
                parts.append(f"self.{field['name']}")
        singleLine = f"        return hash(({', '.join(parts)}))\n"
        if len(singleLine.rstrip("\n")) <= 88:
            lines.append(singleLine)
        else:
            lines.append("        return hash(\n            (\n")
            for part in parts:
                lines.append(f"                {part},\n")
            lines.append("            )\n        )\n")
    else:
        lines.append("        return hash(type(self))\n")

    for helper in model.get("helpers", []):
        lines.append("\n")
        lines.append(PYTHON_HELPERS[helper]["code"])

    return lines


def _collect_python_typing(spec: TypeSpec, imports: set) -> None:
    if spec.kind == "list":
        imports.add("List")
        assert spec.inner is not None
        _collect_python_typing(spec.inner, imports)
    elif spec.kind == "optional":
        imports.add("Optional")
        assert spec.inner is not None
        _collect_python_typing(spec.inner, imports)


def _record_refs(spec: TypeSpec) -> Iterable[TypeSpec]:
    if spec.kind == "record":
        yield spec
    elif spec.inner is not None:
        yield from _record_refs(spec.inner)


# ---------------------------------------------------------------------------
# Java generation
# ---------------------------------------------------------------------------


JAVA_HEADER = """// SPDX-FileCopyrightText: 2025 Dan Peled
// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.
"""


JAVA_LINE_LIMIT = 100


def render_java_model(model: Dict[str, Any]) -> str:
    imports: set = set()
    if any(
        field.get("javaName", field["name"]) != field["name"]
        for field in model["fields"]
    ):
        imports.add("com.fasterxml.jackson.annotation.JsonProperty")
    for helper in model.get("helpers", []):
        imports.update(JAVA_HELPERS[helper]["imports"])

    usesArrays = any(is_array(parse_type(field["type"])) for field in model["fields"])
    usesObjects = any(
        is_reference(parse_type(field["type"]))
        and not is_array(parse_type(field["type"]))
        for field in model["fields"]
    )
    if usesArrays:
        imports.add("java.util.Arrays")
    if usesObjects:
        imports.add("java.util.Objects")

    lines: List[str] = [JAVA_HEADER, "\n"]
    lines.append(f"package {model['javaPackage']};\n\n")
    for imported in sorted(imports):
        lines.append(f"import {imported};\n")
    lines.append("\n")

    doc = model.get("doc", "")
    if doc:
        lines.append(_java_doc_block(doc, ""))
    lines.append(f"public class {model['name']} {{\n")

    for field in model["fields"]:
        lines.append("\n")
        if field.get("doc"):
            lines.append(_java_doc_block(field["doc"], "  "))
        javaName = field.get("javaName", field["name"])
        if javaName != field["name"]:
            lines.append(f'  @JsonProperty("{field["name"]}")\n')
        lines.append(f"  public {java_type(parse_type(field['type']))} {javaName};\n")

    lines.append("\n  /** Default constructor. */\n")
    lines.append(f"  public {model['name']}() {{}}\n")

    for helper in model.get("helpers", []):
        lines.append("\n")
        lines.append(JAVA_HELPERS[helper]["code"].rstrip("\n") + "\n")

    lines.append(_render_java_equals(model))
    lines.append(_render_java_hashcode(model))
    lines.append("}\n")
    return "".join(lines)


def _java_doc_block(text: str, indent: str) -> str:
    text = _java_doc(text)
    singleLine = f"{indent}/** {text} */\n"
    if len(singleLine.rstrip("\n")) <= JAVA_LINE_LIMIT:
        return singleLine
    return f"{indent}/**\n{indent} * {text}\n{indent} */\n"


def _java_doc(text: str) -> str:
    return text.replace("*/", "*&#47;")


def _java_equality_expression(field: Dict[str, Any]) -> str:
    name = field.get("javaName", field["name"])
    spec = parse_type(field["type"])
    if is_array(spec):
        return f"Arrays.equals({name}, that.{name})"
    if spec.kind == "double":
        return f"Double.compare({name}, that.{name}) == 0"
    if spec.kind in {"int", "bool"}:
        return f"{name} == that.{name}"
    return f"Objects.equals({name}, that.{name})"


def _java_hash_expression(field: Dict[str, Any]) -> str:
    name = field.get("javaName", field["name"])
    spec = parse_type(field["type"])
    if is_array(spec):
        return f"Arrays.hashCode({name})"
    if spec.kind == "double":
        return f"Double.hashCode({name})"
    if spec.kind == "int":
        return name
    if spec.kind == "bool":
        return f"Boolean.hashCode({name})"
    return f"Objects.hashCode({name})"


def _render_java_equals(model: Dict[str, Any]) -> str:
    name = model["name"]
    lines = [
        "\n  @Override\n",
        "  public boolean equals(Object o) {\n",
        "    if (this == o) return true;\n",
        f"    if (!(o instanceof {name})) return false;\n",
        f"    {name} that = ({name}) o;\n",
    ]
    if not model["fields"]:
        lines.append("    return true;\n")
    else:
        conditions = [_java_equality_expression(field) for field in model["fields"]]
        singleLine = f"    return {' && '.join(conditions)};\n"
        if len(singleLine.rstrip("\n")) <= JAVA_LINE_LIMIT:
            lines.append(singleLine)
        else:
            lines.append(f"    return {conditions[0]}\n")
            for condition in conditions[1:]:
                lines.append(f"        && {condition}\n")
            lines[-1] = lines[-1].rstrip("\n") + ";\n"
    lines.append("  }\n")
    return "".join(lines)


def _render_java_hashcode(model: Dict[str, Any]) -> str:
    lines = [
        "\n  @Override\n",
        "  public int hashCode() {\n",
    ]
    if not model["fields"]:
        lines.append("    return 0;\n")
    else:
        expressions = [_java_hash_expression(field) for field in model["fields"]]
        lines.append(f"    int result = {expressions[0]};\n")
        for expression in expressions[1:]:
            lines.append(f"    result = 31 * result + {expression};\n")
        lines.append("    return result;\n")
    lines.append("  }\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Topics / constants generation
# ---------------------------------------------------------------------------


PYTHON_TOPICS_HEADER = """# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Generated from schema/synapse_lib.json. Do not edit by hand.
# Run `python tools/generate_synapse_lib.py` to regenerate.
"""


def _constant_name(value: str) -> str:
    result = []
    for index, char in enumerate(value):
        if char.isupper() and index and value[index - 1].islower():
            result.append("_")
        result.append(char.upper())
    return "".join(result)


def render_python_topics(schema: Schema) -> str:
    lines = [PYTHON_TOPICS_HEADER, "\nfrom typing import Final\n\n"]
    for tableName, tableKey in schema.tables.items():
        lines.append(f'{_constant_name(tableName)}_TABLE: Final[str] = "{tableKey}"\n')
    lines.append("\n")
    for topicName, topic in schema.topics.items():
        lines.append(f'{_constant_name(topicName)}: Final[str] = "{topic["key"]}"\n')
    lines.append("\n")
    for settingName, setting in schema.settings.items():
        lines.append(
            f'{_constant_name(settingName)}_SETTING: Final[str] = "{setting["key"]}"\n'
        )
    lines.append("\n")
    for pipelineName, pipeline in schema.pipelines.items():
        lines.append(
            f"{_constant_name(pipelineName)}_PIPELINE: Final[str] = "
            f'"{pipeline["typeString"]}"\n'
        )
    return "".join(lines)


JAVA_TOPICS_HEADER = """// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.
"""


def render_java_topics(schema: Schema) -> str:
    # Spotless separates documented fields with a blank line, so each entry is
    # collected independently and joined the same way.
    entries: List[str] = []
    for tableName, tableKey in schema.tables.items():
        entries.append(
            _java_doc_block(f"The {tableKey} NetworkTables subtable.", "  ")
            + f'  public static final String {_constant_name(tableName)}_TABLE = "{tableKey}";\n'
        )
    for topicName, topic in schema.topics.items():
        entries.append(
            _java_doc_block(topic.get("doc", topicName), "  ")
            + f'  public static final String {_constant_name(topicName)} = "{topic["key"]}";\n'
        )
    for settingName, setting in schema.settings.items():
        entries.append(
            _java_doc_block(setting.get("doc", settingName), "  ")
            + f"  public static final String {_constant_name(settingName)}_SETTING = "
            + f'"{setting["key"]}";\n'
        )
    for pipelineName, pipeline in schema.pipelines.items():
        entries.append(
            _java_doc_block(pipeline.get("doc", pipelineName), "  ")
            + f"  public static final String {_constant_name(pipelineName)}_PIPELINE = "
            + f'"{pipeline["typeString"]}";\n'
        )

    lines = [JAVA_TOPICS_HEADER, "\npackage synapse.generated;\n\n"]
    lines.append(
        "/** NetworkTables paths and pipeline type strings used by SynapseLib. */\n"
    )
    lines.append("public final class SynapseApi {\n")
    lines.append("\n".join(entries))
    lines.append("\n  private SynapseApi() {}\n}\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Output planning
# ---------------------------------------------------------------------------


def output_files(schema: Schema, root: Path) -> Dict[Path, str]:
    """Return a mapping of absolute path -> generated content."""
    libRoot = root
    pyRoot = libRoot / "py" / "src"
    javaRoot = libRoot / "src" / "main" / "java"

    files: Dict[Path, str] = {
        pyRoot / "synapselib" / "_generated" / "topics.py": render_python_topics(
            schema
        ),
        javaRoot / "synapse" / "generated" / "SynapseApi.java": render_java_topics(
            schema
        ),
    }

    modelsByModule: Dict[str, List[Dict[str, Any]]] = {}
    for model in schema.models:
        modelsByModule.setdefault(model["pythonModule"], []).append(model)

    for module, models in modelsByModule.items():
        modulePath = pyRoot.joinpath(*module.split("."))
        files[modulePath.with_suffix(".py")] = render_python_module(schema, models)

    for model in schema.models:
        packagePath = javaRoot.joinpath(*model["javaPackage"].split("."))
        files[packagePath / f"{model['name']}.java"] = render_java_model(model)

    return files


def write_or_check(files: Dict[Path, str], check: bool) -> int:
    stale: List[Path] = []
    for path, content in sorted(files.items()):
        if check:
            existing = path.read_text() if path.exists() else ""
            if existing != content:
                stale.append(path)
                diff = difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=f"{path} (generated)",
                )
                sys.stdout.writelines(diff)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    if check and stale:
        print(
            "\nGenerated files are out of date. Run "
            "`python tools/generate_synapse_lib.py` and commit the result.",
            file=sys.stderr,
        )
        return 1
    if check:
        print("Generated files are up to date.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated files are up to date instead of writing them",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="path to the schema (defaults to schema/synapse_lib.json)",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
        help=(
            "path to the synapse runtime package "
            "(defaults to ../synapse_core/src/synapse)"
        ),
    )
    parser.add_argument(
        "--no-runtime",
        action="store_true",
        help="do not read the runtime source; use the committed schema as-is",
    )
    args = parser.parse_args(argv)

    libRoot = Path(__file__).resolve().parent.parent
    schemaPath = args.schema or libRoot / "schema" / "synapse_lib.json"
    runtimeRoot = args.runtime_root or (
        libRoot.parent / "synapse_core" / "src" / "synapse"
    )

    try:
        raw = json.loads(schemaPath.read_text())
        Schema(raw)

        merged = raw
        if not args.no_runtime:
            if runtimeRoot.is_dir():
                modelNames = {
                    model["name"]
                    for model in raw.get("models", [])
                    if isinstance(model, dict) and isinstance(model.get("name"), str)
                }
                runtime = parse_runtime_api(runtimeRoot, modelNames)
                merged, warnings = merge_runtime_schema(raw, runtime)
                for warning in warnings:
                    print(f"warning: {warning}", file=sys.stderr)
            elif args.runtime_root is not None:
                raise SchemaError(f"Runtime source directory not found: {runtimeRoot}")
            else:
                print(
                    f"warning: runtime source not found at {runtimeRoot}; "
                    "using the committed schema",
                    file=sys.stderr,
                )

        schema = Schema(merged)
    except (OSError, json.JSONDecodeError, SchemaError) as error:
        print(f"Failed to load schema: {error}", file=sys.stderr)
        return 2

    files = output_files(schema, libRoot)
    files[schemaPath] = render_schema(merged)
    return write_or_check(files, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
