# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import MagicMock

from synapse.core.settings_api import (
    BooleanConstraint,
    CameraSettings,
    ColorConstraint,
    ColorFormat,
    ConstraintTypeProto,
    EnumeratedConstraint,
    FileConstraint,
    ListConstraint,
    NumberConstraint,
    PipelineSettings,
    StringConstraint,
    ValueTypeProto,
    protoToSettingValue,
    settingField,
    settingToProto,
    settingValueToProto,
)


# ------------------ NumberConstraint ------------------
def test_number_constraint_valid():
    c = NumberConstraint(0, 10)
    result = c.validate(5)
    assert result.isValid
    assert result.normalizedValue == 5


def test_number_constraint_out_of_bounds():
    c = NumberConstraint(0, 10)
    result = c.validate(15)
    assert not result.isValid
    assert result.errorMessage is not None
    assert "is greater than max" in result.errorMessage


def test_number_constraint_with_step():
    c = NumberConstraint(0, 10, step=2)
    result = c.validate(3)
    assert result.isValid
    assert result.normalizedValue == 4  # Snapped


# ------------------ EnumeratedConstraint ------------------
def test_enumerated_constraint_single_valid():
    c = EnumeratedConstraint(["a", "b", "c"])
    result = c.validate("a")
    assert result.isValid


def test_enumerated_constraint_single_invalid():
    c = EnumeratedConstraint(["a", "b", "c"])
    result = c.validate("x")
    assert not result.isValid


# ------------------ ColorConstraint ------------------
def test_color_constraint_hex_valid_string_short():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate("#abc")
    assert result.isValid
    assert result.normalizedValue == "#ABC"


def test_color_constraint_hex_valid_string_full():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate("#aabbcc")
    assert result.isValid
    assert result.normalizedValue == "#AABBCC"


def test_color_constraint_hex_valid_string_with_0x():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate("0xAABBCC")
    assert result.isValid
    assert result.normalizedValue == "#AABBCC"


def test_color_constraint_hex_valid_int():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate(0xAABBCC)
    assert result.isValid
    assert result.normalizedValue == "#AABBCC"


def test_color_constraint_hex_invalid_format():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate("abc")
    assert not result.isValid


def test_color_constraint_hex_invalid_length():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate("#abcd")
    assert not result.isValid


def test_color_constraint_hex_invalid_value():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate("#ghz")
    assert not result.isValid


def test_color_constraint_rgb_tuple_valid():
    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate((10, 20, 30))
    assert result.isValid
    assert result.normalizedValue == (10, 20, 30)


def test_color_constraint_rgb_tuple_invalid_length():
    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate((10, 20))
    assert not result.isValid


def test_color_constraint_rgb_tuple_invalid_type():
    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate((10, "20", 30))
    assert not result.isValid


def test_color_constraint_rgb_value_out_of_range():
    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate((256, 20, 30))
    assert not result.isValid


def test_color_constraint_rgb_string_invalid_format():
    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate("rgb(10,20)")  # missing third value
    assert not result.isValid


def test_color_constraint_rgb_string_with_percent_not_allowed():
    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate("rgb(10%, 20%, 30%)")
    assert not result.isValid


def test_color_constraint_hsv_tuple_invalid_length():
    c = ColorConstraint(formatType=ColorFormat.kHSV)
    result = c.validate((180, 50))
    assert not result.isValid


def test_color_constraint_hsv_tuple_invalid_type():
    c = ColorConstraint(formatType=ColorFormat.kHSV)
    result = c.validate((180, 50, "75"))
    assert not result.isValid


def test_color_constraint_hsv_value_out_of_range():
    c = ColorConstraint(formatType=ColorFormat.kHSV)
    result = c.validate((361, 50, 75))  # Hue > 360
    assert not result.isValid


def test_color_constraint_wrong_type_input():
    c = ColorConstraint(formatType=ColorFormat.kHex)
    result = c.validate(12.34)  # float invalid for hex
    assert not result.isValid

    c = ColorConstraint(formatType=ColorFormat.kRGB)
    result = c.validate(123)  # int invalid for rgb string/tuple
    assert not result.isValid

    c = ColorConstraint(formatType=ColorFormat.kHSV)
    result = c.validate("notacolor")
    assert not result.isValid


def test_color_constraint_to_dict():
    c = ColorConstraint()
    d = c.toDict()
    assert d["type"] == ConstraintTypeProto.COLOR
    assert d["formatType"] == "hex"

    c_rgb = ColorConstraint(formatType=ColorFormat.kRGB)
    d_rgb = c_rgb.toDict()
    assert d_rgb["formatType"] == "rgb"

    c_hsv = ColorConstraint(formatType=ColorFormat.kHSV)
    d_hsv = c_hsv.toDict()
    assert d_hsv["formatType"] == "hsv"


# ------------------ ListConstraint ------------------
def test_list_constraint_valid_length():
    c = ListConstraint(minLength=1, maxLength=3)
    result = c.validate([1, 2])
    assert result.isValid


def test_list_constraint_too_short():
    c = ListConstraint(minLength=2)
    result = c.validate([1])
    assert not result.isValid


def test_list_constraint_too_long():
    c = ListConstraint(maxLength=2)
    result = c.validate([1, 2, 3])
    assert not result.isValid


def test_list_constraint_untyped_accepts_any_values():
    c = ListConstraint()
    result = c.validate([5, 8])
    assert result.isValid


def test_list_constraint_valid_nested_depth_2():
    c = ListConstraint(depth=2)
    result = c.validate([[1, 2], [3, 4]])
    assert result.isValid


def test_list_constraint_invalid_nested_depth_2_wrong_type():
    c = ListConstraint(depth=2)
    result = c.validate([1, 2])  # Should be list of lists
    assert not result.isValid
    assert result.errorMessage is not None
    assert "depth" in result.errorMessage


def test_list_constraint_valid_nested_depth_3():
    c = ListConstraint(depth=3)
    result = c.validate([[[1, 2], [2, 3]], [[1], [3]]])
    assert result.isValid


def test_list_constraint_invalid_nested_depth_3_structure():
    c = ListConstraint(depth=3)
    result = c.validate([[1, 2], [2, 3]])  # Should be list of list of lists
    assert not result.isValid
    assert result.errorMessage is not None
    assert "depth" in result.errorMessage


def test_list_constraint_int_items():
    c = ListConstraint(itemType=int)
    result = c.validate([1, 2, 3])
    assert result.isValid
    assert result.normalizedValue == [1, 2, 3]


def test_list_constraint_int_items_rejects_other_types():
    c = ListConstraint(itemType=int)
    for value in ([1, "2"], [1, 2.5], [True]):
        result = c.validate(value)
        assert not result.isValid


def test_list_constraint_int_items_normalizes_integral_floats():
    c = ListConstraint(itemType=int)
    result = c.validate([1.0, 2.0])
    assert result.isValid
    assert result.normalizedValue == [1, 2]
    assert result.normalizedValue is not None
    assert all(isinstance(value, int) for value in result.normalizedValue)


def test_list_constraint_float_items():
    c = ListConstraint(itemType=float)
    result = c.validate([1, 2.5])
    assert result.isValid
    assert result.normalizedValue == [1.0, 2.5]


def test_list_constraint_string_items():
    c = ListConstraint(itemType=str)
    result = c.validate(["alpha", "beta"])
    assert result.isValid
    assert not c.validate(["alpha", 2]).isValid


def test_list_constraint_bool_items():
    c = ListConstraint(itemType=bool)
    result = c.validate([True, "false", 0, "on"])
    assert result.isValid
    assert result.normalizedValue == [True, False, False, True]


def test_list_constraint_typed_nested_depth():
    c = ListConstraint(itemType=int, depth=2)
    assert c.validate([[1, 2], [3]]).isValid
    assert not c.validate([[1, "two"]]).isValid


def test_list_constraint_serialization():
    c = ListConstraint(itemType=int, minLength=1, maxLength=5, depth=2)

    data = c.toDict()
    assert data["type"] == ConstraintTypeProto.LIST
    assert data["itemType"] == ValueTypeProto.INT.value
    assert data["depth"] == 2

    proto = c.configToProto()
    assert proto.list is not None
    assert proto.list.item_type == ValueTypeProto.INT
    assert proto.list.depth == 2


def test_setting_value_to_proto_typed_empty_list():
    proto = settingValueToProto([], itemType=ValueTypeProto.INT)
    assert proto.array_type == ValueTypeProto.INT
    assert list(proto.int_array_value) == []

    assert protoToSettingValue(proto) == []


def test_setting_value_to_proto_empty_untyped_list():
    proto = settingValueToProto([])
    assert proto.array_type == ValueTypeProto.LIST
    assert protoToSettingValue(proto) == []


def test_setting_value_to_proto_rejects_nested_lists():
    try:
        settingValueToProto([[1, 2], [3, 4]])
    except TypeError as error:
        assert "Nested lists" in str(error)
    else:
        raise AssertionError("Nested lists should not be serializable")


def test_setting_value_to_proto_infers_list_type():
    proto = settingValueToProto([1, 2, 3])
    assert proto.array_type == ValueTypeProto.INT

    boolProto = settingValueToProto([True, False])
    assert boolProto.array_type == ValueTypeProto.BOOL
    assert list(boolProto.bool_array_value) == [True, False]

    floatProto = settingValueToProto([1, 2.5])
    assert floatProto.array_type == ValueTypeProto.FLOAT
    assert list(floatProto.float_array_value) == [1.0, 2.5]


def test_proto_to_setting_value_supports_legacy_arrays():
    legacy = settingValueToProto([1, 2, 3])
    legacy.array_type = ValueTypeProto.UNSPECIFIED
    assert protoToSettingValue(legacy) == [1, 2, 3]


class _ListSettings(PipelineSettings):
    ids = settingField(ListConstraint(itemType=int), default=[])


def test_setting_to_proto_preserves_empty_typed_list():
    meta = settingToProto(_ListSettings.ids, "<Test/> Test")
    assert meta.default is not None
    assert meta.default.array_type == ValueTypeProto.INT
    assert protoToSettingValue(meta.default) == []


# ------------------ StringConstraint ------------------
def test_string_constraint_valid():
    c = StringConstraint(minLength=2, maxLength=5)
    result = c.validate("abc")
    assert result.isValid


def test_string_constraint_too_short():
    c = StringConstraint(minLength=4)
    result = c.validate("abc")
    assert not result.isValid


def test_string_constraint_pattern_valid():
    c = StringConstraint(pattern=r"^abc\d+$")
    result = c.validate("abc123")
    assert result.isValid


def test_string_constraint_pattern_invalid():
    c = StringConstraint(pattern=r"^abc\d+$")
    result = c.validate("xyz")
    assert not result.isValid


# ------------------ BooleanConstraint ------------------
def test_boolean_constraint_true_values():
    c = BooleanConstraint()
    for val in [True, "true", "1", "yes", 1]:
        result = c.validate(val)
        assert result.isValid
        assert result.normalizedValue is True


def test_boolean_constraint_false_values():
    c = BooleanConstraint()
    for val in [False, "false", "0", "no", 0]:
        result = c.validate(val)
        assert result.isValid
        assert result.normalizedValue is False


def test_boolean_constraint_invalid():
    c = BooleanConstraint()
    result = c.validate("maybe")
    assert not result.isValid


# ------------------ FileConstraint ------------------
def _useFileRoot(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(
        "synapse.core.settings_api._getSettingsRoot", lambda: root.resolve()
    )


def test_file_constraint_valid_relative_path(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "file.json").write_text("{}")

    c = FileConstraint(path="config", fileTypes=["json"])
    result = c.validate("config/file.json")

    assert result.isValid
    assert result.normalizedValue == "config/file.json"


def test_file_constraint_normalizes_absolute_path(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    target = tmp_path / "config" / "file.json"
    target.parent.mkdir()
    target.write_text("{}")

    c = FileConstraint(fileTypes={".JSON"})
    result = c.validate(target)

    assert result.isValid
    assert result.normalizedValue == "config/file.json"


def test_file_constraint_allows_empty_and_none_values(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    c = FileConstraint()

    empty_result = c.validate("")
    assert empty_result.isValid
    assert empty_result.normalizedValue == ""

    none_result = c.validate(None)
    assert none_result.isValid
    assert none_result.normalizedValue == ""


def test_file_constraint_rejects_missing_file(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    c = FileConstraint()
    result = c.validate("config/missing.json")

    assert not result.isValid
    assert result.errorMessage is not None
    assert "does not exist" in result.errorMessage


def test_file_constraint_rejects_directory(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    (tmp_path / "config").mkdir()
    c = FileConstraint()
    result = c.validate("config")

    assert not result.isValid
    assert result.errorMessage is not None
    assert "file" in result.errorMessage


def test_file_constraint_rejects_outside_project_root(tmp_path: Path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    _useFileRoot(monkeypatch, root)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")

    c = FileConstraint()
    result = c.validate(outside)

    assert not result.isValid
    assert result.errorMessage is not None
    assert "project" in result.errorMessage


def test_file_constraint_rejects_wrong_file_type(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    (tmp_path / "file.txt").write_text("data")

    c = FileConstraint(fileTypes=["json"])
    result = c.validate("file.txt")

    assert not result.isValid
    assert result.errorMessage is not None
    assert ".json" in result.errorMessage


def test_file_constraint_serialization(tmp_path: Path, monkeypatch):
    c = FileConstraint(path="config/files", fileTypes=["json", ".yaml"])

    data = c.toDict()
    assert data["type"] == ConstraintTypeProto.FILE
    assert data["path"] == "config/files"
    assert data["file_types"] == [".json", ".yaml"]

    restored = FileConstraint.fromDict(data)
    assert restored.path == c.path
    assert restored.fileTypes == c.fileTypes

    proto = c.configToProto()
    assert proto.file is not None
    assert proto.file.path == "config/files"
    assert proto.file.file_types == [".json", ".yaml"]


def test_setting_value_to_proto_path(tmp_path: Path):
    proto = settingValueToProto(tmp_path / "config" / "file.json")
    assert proto.string_value == (tmp_path / "config" / "file.json").as_posix()


# ------------------ Loading settings ------------------
class _LoadedSettings(PipelineSettings):
    x = settingField(NumberConstraint(0, 10), default=5)
    file = settingField(FileConstraint(fileTypes=["json"]), default="")


def test_loaded_settings_values_are_applied(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)
    target = tmp_path / "config" / "file.json"
    target.parent.mkdir()
    target.write_text("{}")

    settings = _LoadedSettings({"x": 8, "file": "config/file.json"})

    assert settings.getSetting("x") == 8.0
    assert settings.getSetting("file") == "config/file.json"


def test_invalid_loaded_setting_keeps_default(tmp_path: Path, monkeypatch):
    _useFileRoot(monkeypatch, tmp_path)

    settings = _LoadedSettings({"x": 99, "file": "config/missing.json"})

    assert settings.getSetting("x") == 5
    assert settings.getSetting("file") == ""


def test_missing_setting_uses_string_none_and_field_default():
    settings = _LoadedSettings()
    missingField = settingField(NumberConstraint(0, 10), default=7)
    missingField.key = "missing"

    assert settings.getSetting("missing") is None
    assert settings.getSetting(missingField) == 7


def test_camera_settings_do_not_share_class_level_settings():
    def cameraWithResolutions(resolutions):
        camera = MagicMock()
        camera.getPropertyMeta.return_value = {}
        camera.getProperties.return_value = []
        camera.getSupportedResolutions.return_value = resolutions
        return camera

    first = CameraSettings()
    second = CameraSettings()
    second.fromCamera(cameraWithResolutions([(640, 480)]))
    first.fromCamera(cameraWithResolutions([(1920, 1080)]))

    assert first.resolution is not second.resolution
    assert isinstance(first.resolution.constraint, EnumeratedConstraint)
    assert isinstance(second.resolution.constraint, EnumeratedConstraint)
    assert "1920x1080" in [
        option.value for option in first.resolution.constraint.options
    ]
    assert "1920x1080" not in [
        option.value for option in second.resolution.constraint.options
    ]


def test_camera_resolution_default_follows_supported_modes():
    camera = MagicMock()
    camera.getPropertyMeta.return_value = {}
    camera.getProperties.return_value = []
    camera.getSupportedResolutions.return_value = [
        (320, 240),
        (640, 480),
        (800, 600),
        (1280, 720),
        (1280, 800),
    ]

    settings = CameraSettings()
    settings.fromCamera(camera)

    options = [option.value for option in settings.resolution.constraint.options]
    assert "1920x1080" not in options
    assert "1280x800" in options
    assert settings.resolution.defaultValue == "1280x800"
    assert settings.getSetting(CameraSettings.resolution) == "1280x800"

    meta = settingToProto(settings.resolution, "<Camera/> Camera Properties")
    assert protoToSettingValue(meta.default) == "1280x800"

    # The class-level template is shared by descriptor lookups and must keep
    # the original preference for cameras that do support 1080p.
    assert CameraSettings.resolution.defaultValue == "1920x1080"


def test_camera_resolution_keeps_valid_configured_value():
    camera = MagicMock()
    camera.getPropertyMeta.return_value = {}
    camera.getProperties.return_value = []
    camera.getSupportedResolutions.return_value = [(640, 480), (1280, 800)]

    settings = CameraSettings({"resolution": "640x480"})
    settings.fromCamera(camera)

    assert settings.getSetting(CameraSettings.resolution) == "640x480"
    assert settings.resolution.defaultValue == "1280x800"


def test_camera_resolution_replaces_unsupported_configured_value():
    camera = MagicMock()
    camera.getPropertyMeta.return_value = {}
    camera.getProperties.return_value = []
    camera.getSupportedResolutions.return_value = [(640, 480), (1280, 800)]

    settings = CameraSettings({"resolution": "1920x1080"})
    settings.fromCamera(camera)

    assert settings.getSetting(CameraSettings.resolution) == "1280x800"


def test_camera_resolution_prefers_1080p_when_supported():
    camera = MagicMock()
    camera.getPropertyMeta.return_value = {}
    camera.getProperties.return_value = []
    camera.getSupportedResolutions.return_value = [(640, 480), (1920, 1080)]

    settings = CameraSettings({"resolution": "640x480"})
    settings.fromCamera(camera)

    assert settings.resolution.defaultValue == "1920x1080"
    assert settings.getSetting(CameraSettings.resolution) == "640x480"
