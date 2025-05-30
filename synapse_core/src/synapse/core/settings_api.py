import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from ntcore import NetworkTable, NetworkTableEntry
from synapse.bcolors import bcolors
from synapse.log import err

PipelineSettingsMapValue = Any

PipelineSettingsMap = Dict[str, PipelineSettingsMapValue]


class ConstraintType(Enum):
    """Enum for different constraint types"""

    kRange = "range"
    kListOptions = "list_options"
    kColor = "color"
    kList = "list"
    kString = "string"
    kBoolean = "boolean"
    kInteger = "integer"
    kFloat = "float"
    kClass = "class"


@dataclass
class ValidationResult:
    """Result of a validation operation"""

    isValid: bool
    errorMessage: Optional[str] = None
    normalizedValue: Any = None


class Constraint(ABC):
    """Base class for all constraints"""

    def __init__(self, constraintType: ConstraintType):
        self.constraintType = constraintType

    @abstractmethod
    def validate(self, value: Any) -> ValidationResult:
        """Validate a value against this constraint"""
        pass

    @abstractmethod
    def toDict(self) -> Dict[str, Any]:
        """Serialize constraint to dictionary"""
        pass


class RangeConstraint(Constraint):
    """Constraint for numeric ranges"""

    def __init__(
        self,
        minValue: Optional[Union[int, float]] = None,
        maxValue: Optional[Union[int, float]] = None,
        step: Optional[Union[int, float]] = None,
    ):
        """
        Initialize a RangeConstraint instance.

        Args:
            minValue (Optional[Union[int, float]]): The minimum allowed value for the range.
                If None, no minimum constraint is applied.
            maxValue (Optional[Union[int, float]]): The maximum allowed value for the range.
                If None, no maximum constraint is applied.
            step (Optional[Union[int, float]]): The step size or increment within the range.
                If None, any value within the range is allowed.

        """
        super().__init__(ConstraintType.kRange)
        self.minValue = minValue
        self.maxValue = maxValue
        self.step = step

    def validate(self, value: Any) -> ValidationResult:
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


class ClassValueConstraint(Constraint):
    """Constraint for values of a specific class"""

    def __init__(self, expectedClass: Type):
        """
        Initialize a ClassValueConstraint instance.

        Args:
            expectedClass (Type): The expected class type that values must be an instance of.

        """
        super().__init__(ConstraintType.kClass)
        self.expectedClass = expectedClass

    def validate(self, value: Any) -> ValidationResult:
        if isinstance(value, self.expectedClass):
            return ValidationResult(True, None, value)
        else:
            return ValidationResult(
                False, f"Value {value} is not of type {self.expectedClass.__name__}"
            )

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "className": f"{self.expectedClass.__module__}.{self.expectedClass.__name__}",
        }


class ListOptionsConstraint(Constraint):
    """Constraint for selecting from predefined options"""

    def __init__(self, options: List[Any], allowMultiple: bool = False):
        """
        Initialize a ListOptionsConstraint instance.

        Args:
            options (List[Any]): The list of predefined valid options to select from.
            allowMultiple (bool, optional): Whether multiple selections are allowed.
                Defaults to False.

        """
        super().__init__(ConstraintType.kListOptions)
        self.options = options
        self.allowMultiple = allowMultiple

    def validate(self, value: Any) -> ValidationResult:
        if self.allowMultiple:
            if not isinstance(value, list):
                return ValidationResult(
                    False, "Value must be a list when multiple selection is allowed"
                )

            invalidItems = [item for item in value if item not in self.options]
            if invalidItems:
                return ValidationResult(False, f"Invalid options: {invalidItems}")

            return ValidationResult(True, None, value)
        else:
            if value not in self.options:
                return ValidationResult(
                    False, f"Value {value} not in allowed options: {self.options}"
                )
            return ValidationResult(True, None, value)

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "options": self.options,
            "allowMultiple": self.allowMultiple,
        }


class ColorFormat(Enum):
    kHex = "hex"
    kRGB = "rgb"
    kHSV = "hsv"


class ColorConstraint(Constraint):
    import re

    """Constraint for color values (hex, rgb, hsv)"""

    RGB_REGEX = re.compile(
        r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", re.IGNORECASE
    )
    HSV_REGEX = re.compile(
        r"^hsv\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", re.IGNORECASE
    )

    def __init__(self, formatType: str = ColorFormat.kHex.value):
        """
        Initialize a ColorConstraint instance.

        Args:
            formatType (str, optional): The expected color format.
                Supported values include "hex", "rgb", "hsv".
                Defaults to "hex".

        """
        super().__init__(ConstraintType.kColor)
        self.formatType: str = formatType

    def validate(self, value: Any) -> ValidationResult:
        if self.formatType == ColorFormat.kHex.value:
            if isinstance(value, int):
                hex_str = f"#{value:06X}"
                return ValidationResult(True, None, hex_str)

            if not isinstance(value, str):
                return ValidationResult(
                    False, "Color value must be a string or integer for hex format"
                )

            value = value.strip()
            if value.startswith("#"):
                hex_part = value[1:]
            elif value.lower().startswith("0x"):
                hex_part = value[2:]
                value = f"#{hex_part}"
            else:
                return ValidationResult(False, "Hex color must start with '#' or '0x'")

            if len(hex_part) not in [3, 6, 8]:
                return ValidationResult(False, "Invalid hex color length")

            try:
                int(hex_part, 16)
                return ValidationResult(True, None, value.upper())
            except ValueError:
                return ValidationResult(False, "Invalid hex color value")

        elif self.formatType == ColorFormat.kRGB.value:
            # Accept tuple of ints (r, g, b)
            if isinstance(value, tuple):
                if len(value) != 3:
                    return ValidationResult(
                        False, "RGB tuple must have exactly 3 elements"
                    )
                if not all(isinstance(v, int) for v in value):
                    return ValidationResult(
                        False, "RGB tuple elements must be integers"
                    )

                r, g, b = value
                if not (0 <= r <= 255):
                    return ValidationResult(False, "Red (r) must be between 0 and 255")
                if not (0 <= g <= 255):
                    return ValidationResult(
                        False, "Green (g) must be between 0 and 255"
                    )
                if not (0 <= b <= 255):
                    return ValidationResult(False, "Blue (b) must be between 0 and 255")

                normalized = f"rgb({r}, {g}, {b})"
                return ValidationResult(True, None, normalized)

            # Or accept string "rgb(r, g, b)"
            if not isinstance(value, str):
                return ValidationResult(
                    False, "RGB color value must be a string or tuple"
                )

            value = value.strip()
            match = self.RGB_REGEX.match(value)
            if not match:
                return ValidationResult(False, "Invalid RGB format")

            r, g, b = map(int, match.groups())
            if not (0 <= r <= 255):
                return ValidationResult(False, "Red (r) must be between 0 and 255")
            if not (0 <= g <= 255):
                return ValidationResult(False, "Green (g) must be between 0 and 255")
            if not (0 <= b <= 255):
                return ValidationResult(False, "Blue (b) must be between 0 and 255")

            normalized = f"rgb({r}, {g}, {b})"
            return ValidationResult(True, None, normalized)

        elif self.formatType == ColorFormat.kHSV.value:
            # Accept tuple of ints (h, s, v)
            if isinstance(value, tuple):
                if len(value) != 3:
                    return ValidationResult(
                        False, "HSV tuple must have exactly 3 elements"
                    )
                if not all(isinstance(v, int) for v in value):
                    return ValidationResult(
                        False, "HSV tuple elements must be integers"
                    )

                h, s, v = value
                if not (0 <= h <= 360):
                    return ValidationResult(False, "Hue (h) must be between 0 and 360")
                if not (0 <= s <= 100):
                    return ValidationResult(
                        False, "Saturation (s) must be between 0 and 100"
                    )
                if not (0 <= v <= 100):
                    return ValidationResult(
                        False, "Value (v) must be between 0 and 100"
                    )

                normalized = f"hsv({h}, {s}, {v})"
                return ValidationResult(True, None, normalized)

            # Or accept string "hsv(h, s, v)" no %
            if not isinstance(value, str):
                return ValidationResult(
                    False, "HSV color value must be a string or tuple"
                )

            value = value.strip()
            match = self.HSV_REGEX.match(value)
            if not match:
                return ValidationResult(
                    False, "Invalid HSV format (must not contain '%')"
                )

            h, s, v = map(int, match.groups())
            if not (0 <= h <= 360):
                return ValidationResult(False, "Hue (h) must be between 0 and 360")
            if not (0 <= s <= 100):
                return ValidationResult(
                    False, "Saturation (s) must be between 0 and 100"
                )
            if not (0 <= v <= 100):
                return ValidationResult(False, "Value (v) must be between 0 and 100")

            normalized = f"hsv({h}, {s}, {v})"
            return ValidationResult(True, None, normalized)

        return ValidationResult(True, None, value)

    def toDict(self) -> Dict[str, Any]:
        return {"type": self.constraintType.value, "formatType": self.formatType}


class ListConstraint(Constraint):
    """Constraint for list values with optional item constraints and nested depth"""

    def __init__(
        self,
        itemConstraint: Optional[Constraint] = None,
        minLength: Optional[int] = None,
        maxLength: Optional[int] = None,
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
        super().__init__(ConstraintType.kList)
        self.itemConstraint = itemConstraint
        self.minLength = minLength
        self.maxLength = maxLength
        self.depth = depth

    def validate(self, value: Any) -> ValidationResult:
        def _validate_list(val, depth) -> ValidationResult:
            if not isinstance(val, list):
                return ValidationResult(False, f"Value must be a list at depth {depth}")

            if self.minLength is not None and len(val) < self.minLength:
                return ValidationResult(
                    False,
                    f"List at depth {depth} must have at least {self.minLength} items",
                )
            if self.maxLength is not None and len(val) > self.maxLength:
                return ValidationResult(
                    False,
                    f"List at depth {depth} must have at most {self.maxLength} items",
                )

            validated_items = []
            for i, item in enumerate(val):
                if depth > 1:
                    result = _validate_list(item, depth - 1)
                elif self.itemConstraint:
                    result = self.itemConstraint.validate(item)
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
            "itemConstraint": self.itemConstraint.toDict()
            if self.itemConstraint
            else None,
            "minLength": self.minLength,
            "maxLength": self.maxLength,
            "depth": self.depth,
        }


class StringConstraint(Constraint):
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
        super().__init__(ConstraintType.kString)
        self.minLength = minLength
        self.maxLength = maxLength
        self.pattern = pattern

    def validate(self, value: Any) -> ValidationResult:
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


class BooleanConstraint(Constraint):
    """Constraint for boolean values"""

    def __init__(self):
        """
        Initialize a BooleanConstraint instance.

        This constraint restricts values to boolean types (True or False).
        """
        super().__init__(ConstraintType.kBoolean)

    def validate(self, value: Any) -> ValidationResult:
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
        return {"type": self.constraintType.value}

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "BooleanConstraint":
        return cls()


@dataclass
class Setting:
    """A single setting with its constraint and metadata

    Attributes:
        key (str): The unique identifier for the setting.
        constraint (Constraint): The constraint that validates the setting's value.
        defaultValue (Any): The default value for the setting.
        description (Optional[str]): A human-readable description of the setting.
        category (Optional[str]): The category under which the setting is grouped.
    """

    key: str
    constraint: Constraint
    defaultValue: Any
    description: Optional[str] = None
    category: Optional[str] = None

    def validate(self, value: Any) -> ValidationResult:
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
    """Main settings API for managing settings with constraints"""

    def __init__(self):
        self.settings: Dict[str, Setting] = {}
        self.values: Dict[str, Any] = {}

    def addSetting(self, setting: Setting):
        """Add a new setting"""
        self.settings[setting.key] = setting
        if setting.key not in self.values:
            self.values[setting.key] = setting.defaultValue

    def setValue(self, key: str, value: Any) -> ValidationResult:
        """Set a setting value with validation"""
        if key not in self.settings:
            return ValidationResult(False, f"Setting '{key}' does not exist")

        result = self.settings[key].validate(value)
        if result.isValid:
            self.values[key] = result.normalizedValue or value

        return result

    def getValue(self, key: str) -> Any:
        """Get a setting value"""
        return self.values.get(key)

    def serialize(self) -> str:
        """Serialize the entire settings configuration to JSON"""
        settings_data = {
            "settings": {
                key: setting.toDict() for key, setting in self.settings.items()
            },
            "values": self.values,
        }
        return json.dumps(settings_data, indent=2)

    def getSettingsSchema(self) -> Dict[str, Any]:
        """Get the schema of all settings (useful for UI generation)"""
        return {key: setting.toDict() for key, setting in self.settings.items()}


def settingField(
    constraint: Constraint,
    default: Any,
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> Setting:
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
    return Setting("", constraint, default, description, category)


class PipelineSettings:
    """Base class for creating pipeline settings collections.

    Attributes:
        brightness (Setting): Brightness setting (0–100).
        exposure (Setting): Exposure setting (0–100).
        saturation (Setting): Saturation setting (0–100).
        orientation (Setting): Orientation setting (0, 90, 180, 270).
        width (Setting): Width setting (e.g., 1280).
        height (Setting): Height setting (e.g., 720).
    """

    brightness = settingField(RangeConstraint(0, 100), default=50)
    exposure = settingField(RangeConstraint(0, 100), default=50)
    saturation = settingField(RangeConstraint(0, 100), default=50)
    orientation = settingField(RangeConstraint(0, 270, 90), default=0)
    width = settingField(RangeConstraint(minValue=0, maxValue=None), default=1280)
    height = settingField(RangeConstraint(minValue=0, maxValue=None), default=720)

    def __init__(self, settings: Optional[PipelineSettingsMap] = None):
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

    def generateSettingsFromMap(self, settingsMap: PipelineSettingsMap) -> None:
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
                    constraint = RangeConstraint(
                        minValue=-1_000_000.0,
                        maxValue=1_000_000.0,
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
                        f"Error validating {bcolors.BOLD}{field}{bcolors.ENDC}"
                        + f"\n\t\t{bcolors.FAIL}{validation.errorMessage}"
                        + f"\n\tSetting {field} as default: {setting.defaultValue}"
                    )

    def sendSettings(self, nt_table: NetworkTable):
        """
        Send all current settings to the provided NetworkTable.

        Args:
            nt_table (NetworkTable): The table to send settings to.
        """
        for key, value in self._settingsApi.values.items():
            PipelineSettings.setEntryValue(nt_table.getEntry(key), value)

    def __getitem__(self, key: str) -> Optional[PipelineSettingsMapValue]:
        """Access a setting's value using dictionary-style indexing."""
        return self.getSetting(key)

    def __setitem__(self, key: str, value: PipelineSettingsMapValue):
        """Set a setting's value using dictionary-style indexing."""
        self.setSetting(key, value)

    def __delitem__(self, key: str):
        """Delete a setting by key."""
        del self.__settings[key]

    def __str__(self) -> str:
        """Return a string representation of the settings dictionary."""
        return str(self.__settings)

    def __contains__(self, key: Any) -> bool:
        """Check if a key is in the settings."""
        return key in self.__settings.keys()

    def getMap(self) -> Dict[str, Setting]:
        """
        Get the internal settings map.

        Returns:
            Dict[str, Setting]: Map of key to Setting objects.
        """
        return self._settingsApi.settings

    def setMap(self, map: Dict[str, Any]) -> None:
        """
        Set the internal raw settings map (unsafe).

        Args:
            map (Dict[str, Any]): The settings map to set.
        """
        self.__settings = map

    @staticmethod
    def setEntryValue(entry: NetworkTableEntry, value):
        """
        Set a NetworkTable entry's value according to its Python type.

        Args:
            entry (NetworkTableEntry): Entry to set.
            value (Any): Value to write to the entry.

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

    def getSetting(self, name: str) -> Optional[Any]:
        """
        Retrieve the value of a setting by name.

        Args:
            name (str): The setting key.

        Returns:
            Optional[Any]: The setting value, or None if not found.
        """
        if name in self._settingsApi.settings.keys():
            return self._settingsApi.getValue(name)
        err(f"'{self.__class__.__name__}' object has no setting '{name}'")
        return None

    def setSetting(self, name: str, value: Any) -> None:
        """
        Set the value of a setting with validation.

        Args:
            name (str): The setting key.
            value (Any): The new value.
        """
        if name in self._settingsApi.settings.keys():
            result = self._settingsApi.setValue(name, value)
            if not result.isValid:
                err(f"Invalid value for {name}: {result.errorMessage}")
        else:
            err(f"'{self.__class__.__name__}' object has no setting '{name}'")

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
