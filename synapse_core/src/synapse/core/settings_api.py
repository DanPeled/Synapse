# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, overload

from betterproto import which_one_of
from ntcore import NetworkTable, NetworkTableEntry
from synapse_net.proto.settings.v1 import (BooleanConstraintProto,
                                           ColorConstraintProto,
                                           ColorFormatProto,
                                           ConstraintConfigProto,
                                           ConstraintProto,
                                           ConstraintTypeProto,
                                           EnumeratedConstraintProto,
                                           ListConstraintProto,
                                           NumberConstraintProto,
                                           SettingMetaProto, SettingValueProto,
                                           StringConstraintProto)
from synapse_net.proto.v1 import CameraProto

from ..bcolors import MarkupColors
from ..log import err
from ..stypes import CameraID, PipelineID
from .camera_factory import CameraPropKeys, PropertyMetaDict, SynapseCamera

SettingsValue = Any

SettingsMap = Dict[str, SettingsValue]
TSettingValueType = TypeVar("TSettingValueType")


@dataclass
class ValidationResult(Generic[TSettingValueType]):
    """Result of a validation operation"""

    isValid: bool
    errorMessage: Optional[str] = None
    normalizedValue: Optional[TSettingValueType] = None


class Constraint(ABC, Generic[TSettingValueType]):
    """Base class for all constraints"""

    def __init__(self, constraintType: ConstraintTypeProto):
        self.constraintType = constraintType

    @abstractmethod
    def validate(self, value: SettingsValue) -> ValidationResult:
        """Validate a value against this constraint"""
        pass

    @abstractmethod
    def toDict(self) -> Dict[str, Any]:
        """Serialize constraint to dictionary"""
        pass

    @abstractmethod
    def configToProto(self) -> ConstraintConfigProto:
        pass


class NumberConstraint(Constraint[Union[float, int]]):
    """Constraint for numeric values inside a provided range"""

    def __init__(
        self,
        minValue: Optional[float] = None,
        maxValue: Optional[float] = None,
        step: Optional[float] = None,
    ):
        """
        Initialize a NumberConstraint instance.

        Args:
            minValue (Optional[Union[int, float]]): The minimum allowed value for the range.
                If None, no minimum constraint is applied.
            maxValue (Optional[Union[int, float]]): The maximum allowed value for the range.
                If None, no maximum constraint is applied.
            step (Optional[Union[int, float]]): The step size or increment within the range.
                If None, any value within the range is allowed.

        """
        super().__init__(ConstraintTypeProto.NUMBER)
        self.minValue = minValue
        self.maxValue = maxValue
        self.step = step

    def validate(self, value: SettingsValue) -> ValidationResult:
        try:
            numValue = float(value)
            if self.minValue is not None and numValue < self.minValue:
                return ValidationResult(
                    False,
                    f"Value {value} is less than minimum {self.minValue}",
                )
            if self.maxValue is not None and numValue > self.maxValue:
                return ValidationResult(
                    False,
                    f"Value {value} is greater than maximum {self.maxValue}",
                )
            if self.step and self.minValue is not None:
                if (numValue - self.minValue) % self.step != 0:
                    # Snap to nearest step
                    steps = round((numValue - self.minValue) / self.step)
                    normalized = self.minValue + (steps * self.step)
                    return ValidationResult(True, None, normalized)

            return ValidationResult(True, None, numValue)
        except (ValueError, TypeError):
            return ValidationResult(False, f"Value {value} is not a valid number")

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "minValue": self.minValue,
            "maxValue": self.maxValue,
            "step": self.step,
        }

    def configToProto(self) -> ConstraintConfigProto:
        return ConstraintConfigProto(
            numeric=NumberConstraintProto(
                min=self.minValue, max=self.maxValue, step=self.step
            )
        )


TEnumeratedType = TypeVar("TEnumeratedType")


class EnumeratedConstraint(Constraint[TEnumeratedType], Generic[TEnumeratedType]):
    """Constraint for selecting from predefined options"""

    def __init__(self, options: List[TEnumeratedType]):
        """
        Initialize a ListOptionsConstraint instance.

        Args:
            options (List[Any]): The list of predefined valid options to select from.
            allowMultiple (bool, optional): Whether multiple selections are allowed.
                Defaults to False.

        """
        super().__init__(ConstraintTypeProto.ENUMERATED)
        self.options = options

    def validate(self, value: SettingsValue) -> ValidationResult:
        expectedType = type(self.options[0])
        if not isinstance(value, expectedType):
            return ValidationResult(
                False, f"Expected type {expectedType}, got {type(value)}"
            )
        if value not in self.options:
            return ValidationResult(
                False, f"Value {value} not in allowed options: {self.options}"
            )
        return ValidationResult(True, None, value)

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "options": self.options,
        }

    def configToProto(self) -> ConstraintConfigProto:
        return ConstraintConfigProto(
            enumerated=EnumeratedConstraintProto(
                options=list(map(lambda op: settingValueToProto(op), self.options)),
            )
        )


class ColorFormat(Enum):
    kHex = "hex"
    kRGB = "rgb"
    kHSV = "hsv"

    def toProtoType(self) -> ColorFormatProto:
        if self == ColorFormat.kHSV:
            return ColorFormatProto.HSV
        elif self == ColorFormat.kHex:
            return ColorFormatProto.HEX
        else:
            return ColorFormatProto.RGB


class ColorConstraint(Constraint[Union[tuple, list]]):
    import re

    """Constraint for color values (hex, rgb, hsv) or ranges of them."""

    RGB_REGEX = re.compile(
        r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", re.IGNORECASE
    )
    HSV_REGEX = re.compile(
        r"^hsv\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", re.IGNORECASE
    )

    def __init__(self, formatType=ColorFormat.kHex, rangeMode: bool = False):
        """
        Initialize a ColorConstraint instance.

        Args:
            formatType (str): Color format ("hex", "rgb", "hsv").
            rangeMode (bool): If True, expects a range (e.g., tuple of two colors).
        """
        super().__init__(ConstraintTypeProto.COLOR)
        self.formatType = formatType
        self.rangeMode = rangeMode

    def validate(self, value: SettingsValue) -> ValidationResult:
        if self.rangeMode:
            if not (isinstance(value, (tuple, list)) and len(value) == 2):
                return ValidationResult(False, "Range must be a (lower, upper) tuple")

            low_result = self._validate_single(value[0])
            if not low_result.isValid:
                return ValidationResult(
                    False, f"Lower bound error: {low_result.errorMessage}"
                )

            high_result = self._validate_single(value[1])
            if not high_result.isValid:
                return ValidationResult(
                    False, f"Upper bound error: {high_result.errorMessage}"
                )

            return ValidationResult(
                True, None, (low_result.normalizedValue, high_result.normalizedValue)
            )

        # Single value mode
        return self._validate_single(value)

    def _validate_single(self, value: SettingsValue) -> ValidationResult:
        if self.formatType == ColorFormat.kHex:
            if isinstance(value, int):
                hex_str = f"#{value:06X}"
                return ValidationResult(True, None, hex_str)

            if not isinstance(value, str):
                return ValidationResult(False, "Hex value must be string or int")

            value = value.strip()
            if value.startswith("#"):
                hex_part = value[1:]
            elif value.lower().startswith("0x"):
                hex_part = value[2:]
                value = f"#{hex_part}"
            else:
                return ValidationResult(False, "Hex must start with '#' or '0x'")

            if len(hex_part) not in [3, 6, 8]:
                return ValidationResult(False, "Invalid hex length")

            try:
                int(hex_part, 16)
                return ValidationResult(True, None, value.upper())
            except ValueError:
                return ValidationResult(False, "Invalid hex digits")

        elif self.formatType == ColorFormat.kRGB:
            if isinstance(value, tuple):
                if len(value) != 3 or not all(isinstance(v, int) for v in value):
                    return ValidationResult(False, "RGB must be tuple of 3 ints")
                r, g, b = value
                if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                    return ValidationResult(False, "RGB components must be in 0–255")
                return ValidationResult(True, None, tuple(value))

            if isinstance(value, str):
                match = self.RGB_REGEX.match(value.strip())
                if match:
                    r, g, b = map(int, match.groups())
                    return self._validate_single((r, g, b))
                return ValidationResult(False, "Invalid RGB string format")

            return ValidationResult(False, "Invalid RGB format")

        elif self.formatType == ColorFormat.kHSV:
            if isinstance(value, tuple):
                if len(value) != 3 or not all(isinstance(v, int) for v in value):
                    return ValidationResult(False, "HSV must be tuple of 3 ints")
                h, s, v = value
                if not (0 <= h <= 179 and 0 <= s <= 255 and 0 <= v <= 255):
                    return ValidationResult(
                        False, "HSV components must be in OpenCV range"
                    )
                return ValidationResult(True, None, tuple(value))

            if isinstance(value, str):
                match = self.HSV_REGEX.match(value.strip())
                if match:
                    h, s, v = map(int, match.groups())
                    return self._validate_single((h, s, v))
                return ValidationResult(False, "Invalid HSV string format")

            return ValidationResult(False, "Invalid HSV format")

        return ValidationResult(False, f"Unknown formatType: {self.formatType}")

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "formatType": self.formatType.value,
            "rangeMode": self.rangeMode,
        }

    def configToProto(self) -> ConstraintConfigProto:
        return ConstraintConfigProto(
            color=ColorConstraintProto(
                format=self.formatType.toProtoType(), range_mode=self.rangeMode
            )
        )


class ListConstraint(Constraint[List]):
    """Constraint for list values with optional item constraints and nested depth"""

    def __init__(
        self,
        minLength: int = 0,
        maxLength: int = 0,
        depth: int = 1,
    ):
        """
        Initialize a ListConstraint instance.

        Args:
            itemConstraint (Optional[Constraint]): A constraint that each item in the list must satisfy.
                If None, no per-item constraint is applied.
            minLength (Optional[int]): The minimum number of items allowed in the list.
                If None, no minimum constraint is applied.
            maxLength (Optional[int]): The maximum number of items allowed in the list.
                If None, no maximum constraint is applied.
            depth (int): The allowed level of list nesting. For example, a depth of 2 means a 2D list.
                Defaults to 1.

        """
        super().__init__(ConstraintTypeProto.LIST)
        self.minLength = minLength
        self.maxLength = maxLength
        self.depth = depth

    def validate(self, value: SettingsValue) -> ValidationResult:
        def _validate_list(val, depth) -> ValidationResult:
            if not isinstance(val, list):
                return ValidationResult(False, f"Value must be a list at depth {depth}")

            if self.minLength > 0 and len(val) < self.minLength:
                return ValidationResult(
                    False,
                    f"List at depth {depth} must have at least {self.minLength} items",
                )
            if self.maxLength > 0 and len(val) > self.maxLength:
                return ValidationResult(
                    False,
                    f"List at depth {depth} must have at most {self.maxLength} items",
                )

            validated_items = []
            for i, item in enumerate(val):
                if depth > 1:
                    result = _validate_list(item, depth - 1)
                else:
                    result = ValidationResult(True, None, item)

                if not result.isValid:
                    return ValidationResult(
                        False, f"Item at index {i}: {result.errorMessage}"
                    )
                validated_items.append(
                    result.normalizedValue
                    if result.normalizedValue is not None
                    else item
                )

            return ValidationResult(True, None, validated_items)

        return _validate_list(value, self.depth)

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "minLength": self.minLength,
            "maxLength": self.maxLength,
            "depth": self.depth,
        }

    def configToProto(self) -> ConstraintConfigProto:
        return ConstraintConfigProto(
            list=ListConstraintProto(
                min_length=self.minLength,
                max_length=self.maxLength,
            )
        )


class StringConstraint(Constraint[str]):
    """Constraint for string values"""

    def __init__(
        self,
        minLength: Optional[int] = None,
        maxLength: Optional[int] = None,
        pattern: Optional[str] = None,
    ):
        """
        Initialize a StringConstraint instance.

        Args:
            minLength (Optional[int]): The minimum number of characters allowed in the string.
                If None, no minimum length constraint is applied.
            maxLength (Optional[int]): The maximum number of characters allowed in the string.
                If None, no maximum length constraint is applied.
            pattern (Optional[str]): A regular expression pattern that the string must match.
                If None, no pattern constraint is applied.

        """
        super().__init__(ConstraintTypeProto.STRING)
        self.minLength = minLength
        self.maxLength = maxLength
        self.pattern = pattern

    def validate(self, value: SettingsValue) -> ValidationResult:
        if not isinstance(value, str):
            return ValidationResult(False, "Value must be a string")

        if self.minLength is not None and len(value) < self.minLength:
            return ValidationResult(
                False, f"String must be at least {self.minLength} characters"
            )

        if self.maxLength is not None and len(value) > self.maxLength:
            return ValidationResult(
                False, f"String must be at most {self.maxLength} characters"
            )

        if self.pattern:
            import re

            if not re.match(self.pattern, value):
                return ValidationResult(False, "String does not match required pattern")

        return ValidationResult(True, None, value)

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "minLength": self.minLength,
            "maxLength": self.maxLength,
            "pattern": self.pattern,
        }

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "StringConstraint":
        return cls(data.get("minLength"), data.get("maxLength"), data.get("pattern"))

    def configToProto(self) -> ConstraintConfigProto:
        return ConstraintConfigProto(
            string=StringConstraintProto(
                min_length=self.minLength,
                max_length=self.maxLength,
                pattern=self.pattern,
            )
        )


class BooleanConstraint(Constraint[bool]):
    """Constraint for boolean values"""

    def __init__(self, renderAsButton: bool = False):
        """
        Initialize a BooleanConstraint instance.

        This constraint restricts values to boolean types (True or False).
        """
        super().__init__(ConstraintTypeProto.BOOLEAN)
        self.renderAsButton = renderAsButton

    def validate(self, value: SettingsValue) -> ValidationResult:
        if isinstance(value, bool):
            return ValidationResult(True, None, value)

        # Try to convert common representations
        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ["true", "1", "yes", "on"]:
                return ValidationResult(True, None, True)
            elif lower_val in ["false", "0", "no", "off"]:
                return ValidationResult(True, None, False)

        if isinstance(value, (int, float)):
            return ValidationResult(True, None, bool(value))

        return ValidationResult(False, "Value cannot be converted to boolean")

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "render_as_button": self.renderAsButton,
        }

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "BooleanConstraint":
        return cls(data["render_as_button"])

    def configToProto(self) -> ConstraintConfigProto:
        return ConstraintConfigProto(
            boolean=BooleanConstraintProto(self.renderAsButton)
        )


TConstraintType = TypeVar("TConstraintType", bound=Constraint)


@dataclass
class Setting(Generic[TConstraintType, TSettingValueType]):
    """A single setting with its constraint and metadata

    Attributes:
        key (str): The unique identifier for the setting.
        constraint (Constraint): The constraint that validates the setting's value.
        defaultValue (Any): The default value for the setting.
        description (Optional[str]): A human-readable description of the setting.
        category (Optional[str]): The category under which the setting is grouped.
    """

    key: str
    constraint: TConstraintType
    defaultValue: TSettingValueType
    description: Optional[str] = None
    category: Optional[str] = None

    def validate(self, value: SettingsValue) -> ValidationResult:
        return self.constraint.validate(value)

    def toDict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "constraint": self.constraint.toDict(),
            "defaultValue": self.defaultValue,
            "description": self.description,
            "category": self.category,
        }


class SettingsAPI:
    """Main settings API for managing settings with constraints.

    This class provides methods to register new settings, validate
    and assign values to them, and serialize the current configuration.
    """

    def __init__(self):
        """Initializes the SettingsAPI with empty settings and values dictionaries."""
        self.settings: Dict[str, Setting] = {}
        self.values: Dict[str, Any] = {}

    def addSetting(self, setting: Setting) -> None:
        """Adds a new setting to the API.

        If a default value is specified and no value is already set,
        the default is used.

        Args:
            setting (Setting): The setting to add.
        """
        self.settings[setting.key] = setting
        if setting.key not in self.values:
            self.values[setting.key] = setting.defaultValue

    def setValue(self, key: str, value: SettingsValue) -> ValidationResult:
        """Sets the value of a setting with validation.

        Args:
            key (str): The key of the setting to update.
            value (SettingsValue): The value to assign to the setting.

        Returns:
            ValidationResult: The result of the validation process, including
            whether the value is valid and the normalized value if applicable.
        """
        if key not in self.settings:
            return ValidationResult(False, f"Setting '{key}' does not exist")

        result = self.settings[key].validate(value)
        if result.isValid:
            self.values[key] = result.normalizedValue or value

        return result

    def getSetting(self, prop: str) -> Optional[Setting]:
        """Retrieves the setting object for a given key.

        Args:
            prop (str): The key of the setting to retrieve.

        Returns:
            Optional[Setting]: The Setting object if found, otherwise None.
        """
        return self.settings.get(prop)

    def getValue(self, key: str) -> Any:
        """Retrieves the current value of a setting.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Any: The current value assigned to the setting, or None if not set.
        """
        return self.values.get(key)

    def serialize(self) -> str:
        """Serializes all settings and their current values to a JSON string.

        Returns:
            str: A JSON-formatted string representing the settings and values.
        """
        settings_data = {
            "settings": {
                key: setting.toDict() for key, setting in self.settings.items()
            },
            "values": self.values,
        }
        return json.dumps(settings_data, indent=2)

    def getSettingsSchema(self) -> Dict[str, Any]:
        """Retrieves the schema of all registered settings.

        Useful for generating user interfaces or validation tools.

        Returns:
            Dict[str, Any]: A dictionary mapping setting keys to their schema representations.
        """
        return {key: setting.toDict() for key, setting in self.settings.items()}


def settingField(
    constraint: Constraint[TSettingValueType],
    default: TSettingValueType,
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> Setting[Constraint[TSettingValueType], TSettingValueType]:
    """
    Creates a Setting instance for use in SettingsCollection classes.

    Args:
        constraint (Constraint): A constraint that validates the value of the setting.
        default (Any): The default value for the setting.
        description (Optional[str]): An optional human-readable description of the setting.
        category (Optional[str]): An optional category to group the setting under.

    Returns:
        Setting: A new Setting object with the specified configuration.
    """
    return Setting[Constraint[TSettingValueType], TSettingValueType](
        "", constraint, default, description, category
    )


class SettingsCollection:
    def __init__(self, settings: Optional[SettingsMap] = None):
        """
        Initialize the PipelineSettings instance.

        Args:
            settings (Optional[PipelineSettingsMap]): Initial settings map to load values from.
        """
        self._settingsApi = SettingsAPI()
        self._fieldNames = []
        self._initializeSettings()

        if settings:
            self.generateSettingsFromMap(settings)

    def generateSettingsFromMap(self, settingsMap: SettingsMap) -> None:
        """
        Populate the settings from a given map, generating constraints dynamically if necessary.

        Args:
            settingsMap (PipelineSettingsMap): A dictionary of setting keys to values.
        """
        prexistingKeys = self.getSchema().keys()
        for field, value in settingsMap.items():
            if field not in prexistingKeys:
                constraint: Optional[Constraint] = None
                if isinstance(value, bool):
                    constraint = BooleanConstraint()
                elif isinstance(value, float | int):
                    constraint = NumberConstraint(
                        minValue=None,
                        maxValue=None,
                        step=None if isinstance(value, float) else 1,
                    )
                elif isinstance(value, str):
                    constraint = StringConstraint()
                elif isinstance(value, list):

                    def getListDepth(value) -> int:
                        if not isinstance(value, list):
                            return 0
                        if not value:
                            return 1
                        return 1 + max(getListDepth(item) for item in value)

                    constraint = ListConstraint(depth=getListDepth(value))
                if constraint is not None:
                    self._settingsApi.addSetting(
                        Setting(key=field, constraint=constraint, defaultValue=value)
                    )
            else:
                setting = self._settingsApi.settings[field]
                validation = setting.validate(value)
                if validation.errorMessage is None:
                    self._settingsApi.setValue(field, value)
                else:
                    err(
                        f"Error validating {MarkupColors.bold(field)}"
                        + f"\n\t\t{validation.errorMessage}"
                        + f"\n\tSetting {field} as default: {setting.defaultValue}"
                    )

    def sendSettings(self, nt_table: NetworkTable):
        """
        Send all current settings to the provided NetworkTable.

        Args:
            nt_table (NetworkTable): The table to send settings to.
        """
        for key, value in self._settingsApi.values.items():
            setEntryValue(nt_table.getEntry(key), value)

    def __getitem__(self, key: Union[str, Setting]) -> Optional[SettingsValue]:
        """Access a setting's value using dictionary-style indexing."""
        return self.getSetting(key)

    def __setitem__(self, key: Union[str, Setting], value: SettingsValue):
        """Set a setting's value using dictionary-style indexing."""
        self.setSetting(key, value)

    def __contains__(self, setting: Union[str, Setting]) -> bool:
        """Check if a key is in the settings."""
        key = setting if isinstance(setting, str) else setting.key
        return key in self._settingsApi.settings.keys()

    def getMap(self) -> Dict[str, Setting]:
        """
        Get the internal settings map.

        Returns:
            Dict[str, Setting]: Map of key to Setting objects.
        """
        return self._settingsApi.settings

    def _initializeSettings(self):
        """Initialize declared settings by inspecting class-level attributes."""
        for attrName in dir(self.__class__):
            if not attrName.startswith("_"):
                attrValue = getattr(self.__class__, attrName)
                if isinstance(attrValue, Setting):
                    if attrValue.key != attrName:
                        attrValue.key = attrName
                    self._settingsApi.addSetting(attrValue)
                    self._fieldNames.append(attrName)

    @overload
    def getSetting(self, setting: str) -> Optional[Any]: ...

    @overload
    def getSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getSetting(self, setting: Union[str, Setting]) -> Optional[Any]:
        """
        Retrieve a setting's value by key or Setting instance.

        Args:
            setting (Union[str, Setting]): Key or Setting.

        Returns:
            Optional[Any]: Value if found, otherwise None or default.
        """
        key = setting if isinstance(setting, str) else setting.key
        if key in self._settingsApi.settings.keys():
            return self._settingsApi.getValue(key)
        err(f"'{self.__class__.__name__}' object has no setting '{key}'")
        return None if isinstance(setting, str) else setting.defaultValue

    def setSetting(self, setting: Union[Setting, str], value: SettingsValue) -> None:
        """
        Set a setting’s value with validation.

        Args:
            setting (Union[str, Setting]): Setting key or object.
            value (SettingsValue): Value to assign.
        """
        key = setting if isinstance(setting, str) else setting.key
        if key in self._settingsApi.settings.keys():
            result = self._settingsApi.setValue(key, value)
            if not result.isValid:
                err(f"Invalid value for {setting}: {result.errorMessage}")
        else:
            err(f"'{self.__class__.__name__}' object has no setting '{setting}'")

    def validate(self, **kwargs) -> Dict[str, ValidationResult]:
        """
        Validate a batch of values.

        Args:
            **kwargs: Mapping of keys to values.

        Returns:
            Dict[str, ValidationResult]: Results for each key.
        """
        results = {}
        for key, value in kwargs.items():
            if key in self._settingsApi.settings.keys():
                results[key] = self._settingsApi.settings[key].validate(value)
            else:
                results[key] = ValidationResult(False, f"Unknown setting: {key}")
        return results

    def update(self, **kwargs) -> Dict[str, ValidationResult]:
        """
        Update settings values with validation.

        Args:
            **kwargs: Mapping of keys to new values.

        Returns:
            Dict[str, ValidationResult]: Validation results for each updated key.
        """
        results = {}
        for key, value in kwargs.items():
            if key in self._settingsApi.settings.keys():
                results[key] = self._settingsApi.setValue(key, value)
            else:
                results[key] = ValidationResult(False, f"Unknown setting: {key}")
        return results

    def toDict(self) -> Dict[str, Any]:
        """
        Convert the current setting values to a dictionary.

        Returns:
            Dict[str, Any]: Mapping of key to value.
        """
        return {name: self.getSetting(name) for name in self._fieldNames}

    def fromDict(self, data: Dict[str, Any]) -> Dict[str, ValidationResult]:
        """
        Update the settings from a dictionary.

        Args:
            data (Dict[str, Any]): Key-value pairs to apply.

        Returns:
            Dict[str, ValidationResult]: Validation results.
        """
        return self.update(**data)

    def serialize(self) -> str:
        """
        Serialize the settings to a JSON string.

        Returns:
            str: The serialized settings.
        """
        return self._settingsApi.serialize()

    def getSchema(self) -> Dict[str, Any]:
        """
        Get the schema for all settings.

        Returns:
            Dict[str, Any]: Dictionary of schema information.
        """
        return self._settingsApi.getSettingsSchema()

    def resetToDefaults(self):
        """Reset all settings to their default values."""
        for name in self._fieldNames:
            setting = self._settingsApi.settings[name]
            self._settingsApi.values[name] = setting.defaultValue

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the settings.

        Returns:
            str: Representation string.
        """
        values = {name: self.getSetting(name) for name in self._fieldNames}
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in values.items())})"

    def getAPI(self) -> SettingsAPI:
        return self._settingsApi


def setEntryValue(entry: NetworkTableEntry, value):
    """
    Set a NetworkTable entry's value according to its Python type.

    Args:
        entry (NetworkTableEntry): Entry to set.
        value (SettingsValue): Value to write to the entry.

    Raises:
        ValueError: If the value type is unsupported.
    """
    if isinstance(value, int):
        entry.setInteger(value)
    elif isinstance(value, float):
        entry.setFloat(value)
    elif isinstance(value, bool):
        entry.setBoolean(value)
    elif isinstance(value, str):
        entry.setString(value)
    elif isinstance(value, list):
        if all(isinstance(i, int) for i in value):
            entry.setIntegerArray(value)
        elif all(isinstance(i, float) for i in value):
            entry.setFloatArray(value)
        elif all(isinstance(i, bool) for i in value):
            entry.setBooleanArray(value)
        elif all(isinstance(i, str) for i in value):
            entry.setStringArray(value)
        else:
            raise ValueError("Unsupported list type")
    else:
        raise ValueError("Unsupported type")


class CameraSettings(SettingsCollection):
    kCameraPropsCategory = "Camera Properties"

    brightness = settingField(
        NumberConstraint(0, 100),
        default=50,
        category=kCameraPropsCategory,
        description="Adjusts the brightness level of the image.",
    )
    exposure = settingField(
        NumberConstraint(0, 100),
        default=50,
        category=kCameraPropsCategory,
        description="Controls the exposure level.",
    )
    saturation = settingField(
        NumberConstraint(0, 100),
        default=50,
        category=kCameraPropsCategory,
        description="Changes the intensity of color saturation.",
    )
    sharpness = settingField(
        NumberConstraint(0, 100),
        default=50,
        category=kCameraPropsCategory,
        description="Determines the sharpness of the image.",
    )
    gain = settingField(
        NumberConstraint(0, 100),
        default=50,
        category=kCameraPropsCategory,
        description="Amplifies the signal brightness.",
    )
    orientation = settingField(
        EnumeratedConstraint(options=[0, 90, 180, 270]),
        default=0,
        category=kCameraPropsCategory,
        description="Rotates the image orientation (0, 90, 180, 270 degrees).",
    )
    resolution = settingField(
        EnumeratedConstraint(
            options=[
                "1920x1080",
                "1640x1232",
                "1296x972",
                "1280x960",
                "1280x720",
                "1024x768",
                "800x600",
                "640x480",
                "640x360",
                "320x240",
                "320x180",
            ]
        ),
        default="1920x1080",
        category=kCameraPropsCategory,
        description="Camera Resolution",
    )

    def fromCamera(self, camera: SynapseCamera):
        def getPropNumberConstraint(
            propMeta: PropertyMetaDict, prop: str
        ) -> NumberConstraint:
            if prop not in propMeta:
                return NumberConstraint(0, 100, 1)
            else:
                propData = propMeta.get(prop)
                assert propData is not None

                return NumberConstraint(propData["min"], propData["max"], step=None)

        propMeta = camera.getPropertyMeta()
        if propMeta is not None:
            self.brightness.constraint = getPropNumberConstraint(
                propMeta, CameraPropKeys.kBrightness.value
            )
            self.exposure.constraint = getPropNumberConstraint(
                propMeta, CameraPropKeys.kBrightness.value
            )
            self.saturation.constraint = getPropNumberConstraint(
                propMeta, CameraPropKeys.kBrightness.value
            )
            self.sharpness.constraint = getPropNumberConstraint(
                propMeta, CameraPropKeys.kBrightness.value
            )
            self.gain.constraint = getPropNumberConstraint(
                propMeta, CameraPropKeys.kBrightness.value
            )
        self.resolution.constraint = EnumeratedConstraint(
            options=list(
                set(map(lambda s: f"{s[0]}x{s[1]}", camera.getSupportedResolutions()))
            )
        )


class PipelineSettings(SettingsCollection):
    """Base class for creating pipeline settings collections."""

    def __init__(self, settings: Optional[SettingsMap] = None):
        super().__init__(settings)


def protoToSettingValue(proto: SettingValueProto) -> SettingsValue:
    scalar_field = which_one_of(proto, "scalar_value")

    if scalar_field is not None:
        return scalar_field[1]
    if proto.int_array_value:
        return list(proto.int_array_value)
    elif proto.string_array_value:
        return list(proto.string_array_value)
    elif proto.bool_array_value:
        return list(proto.bool_array_value)
    elif proto.float_array_value:
        return list(proto.float_array_value)
    elif proto.bytes_array_value:
        return list(proto.bytes_array_value)

    raise ValueError("No value set in SettingValueProto")


def settingValueToProto(val: SettingsValue) -> SettingValueProto:
    proto = SettingValueProto()

    if isinstance(val, int):
        proto.int_value = val
    elif isinstance(val, str):
        proto.string_value = val
    elif isinstance(val, bool):
        proto.bool_value = val
    elif isinstance(val, float):
        proto.float_value = val
    elif isinstance(val, bytes):
        proto.bytes_value = val
    elif isinstance(val, list):
        if all(isinstance(v, int) for v in val):
            proto.int_array_value = val
        elif all(isinstance(v, str) for v in val):
            proto.string_array_value = val
        elif all(isinstance(v, bool) for v in val):
            proto.bool_array_value = val
        elif all(isinstance(v, float) for v in val):
            proto.float_array_value = val
        elif all(isinstance(v, bytes) for v in val):
            proto.bytes_array_value = val
        else:
            raise TypeError("Unsupported list element type")
    else:
        raise TypeError(f"Unsupported type: {type(val)}")

    return proto


def constraintToProto(constraint: Constraint) -> ConstraintProto:
    return ConstraintProto(
        type=constraint.constraintType, constraint=constraint.configToProto()
    )


def settingToProto(setting: Setting, defaultCategory: str) -> SettingMetaProto:
    return SettingMetaProto(
        name=setting.key,
        description=setting.description or "",
        category=setting.category or defaultCategory,
        constraint=constraintToProto(setting.constraint),
        default=settingValueToProto(setting.defaultValue),
    )


def settingsToProto(
    settings: SettingsCollection, typename: str
) -> List[SettingMetaProto]:
    result = []
    api = settings.getAPI()

    for schema in api.settings.values():
        if schema is not None:
            result.append(settingToProto(schema, typename))

    return result


def cameraToProto(
    camid: CameraID,
    name: str,
    camera: SynapseCamera,
    pipelineIndex: PipelineID,
    defaultPipeline: PipelineID,
    kind: str,
) -> CameraProto:
    cameraSettingsMetaValue = CameraSettings()
    cameraSettingsMetaValue.fromCamera(camera)
    return CameraProto(
        name=name,
        index=camid,
        stream_path=camera.stream,
        kind=kind,
        pipeline_index=pipelineIndex,
        default_pipeline=defaultPipeline,
        max_fps=int(camera.getMaxFPS()),
        settings=settingsToProto(
            typename="Camera Props", settings=cameraSettingsMetaValue
        ),
    )
