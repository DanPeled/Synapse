import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ntcore import NetworkTable, NetworkTableEntry


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

    @classmethod
    @abstractmethod
    def fromDict(cls, data: Dict[str, Any]) -> "Constraint":
        """Deserialize constraint from dictionary"""
        pass


class RangeConstraint(Constraint):
    """Constraint for numeric ranges"""

    def __init__(
        self,
        minValue: Union[int, float],
        maxValue: Union[int, float],
        step: Optional[Union[int, float]] = None,
    ):
        super().__init__(ConstraintType.kRange)
        self.minValue = minValue
        self.maxValue = maxValue
        self.step = step

    def validate(self, value: Any) -> ValidationResult:
        try:
            numValue = float(value)
            if numValue < self.minValue or numValue > self.maxValue:
                return ValidationResult(
                    False,
                    f"Value {value} is outside range [{self.minValue}, {self.maxValue}]",
                )

            if self.step and (numValue - self.minValue) % self.step != 0:
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

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "RangeConstraint":
        return cls(data["minValue"], data["maxValue"], data.get("step"))


class ListOptionsConstraint(Constraint):
    """Constraint for selecting from predefined options"""

    def __init__(self, options: List[Any], allowMultiple: bool = False):
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

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "ListOptionsConstraint":
        return cls(data["options"], data.get("allowMultiple", False))


class ColorConstraint(Constraint):
    """Constraint for color values (hex, rgb, etc.)"""

    def __init__(self, formatType: str = "hex"):
        super().__init__(ConstraintType.kColor)
        self.formatType = formatType  # "hex", "rgb", "rgba", "hsl"

    def validate(self, value: Any) -> ValidationResult:
        if not isinstance(value, str):
            return ValidationResult(False, "Color value must be a string")

        value = value.strip()

        if self.formatType == "hex":
            if not value.startswith("#") or len(value) not in [4, 7, 9]:
                return ValidationResult(False, "Invalid hex color format")
            try:
                int(value[1:], 16)
                return ValidationResult(True, None, value.upper())
            except ValueError:
                return ValidationResult(False, "Invalid hex color value")

        elif self.formatType == "rgb":
            if not (value.startswith("rgb(") and value.endswith(")")):
                return ValidationResult(False, "Invalid RGB format")
            # Add more RGB validation logic as needed

        return ValidationResult(True, None, value)

    def toDict(self) -> Dict[str, Any]:
        return {"type": self.constraintType.value, "formatType": self.formatType}

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "ColorConstraint":
        return cls(data.get("formatType", "hex"))


class ListConstraint(Constraint):
    """Constraint for list values with optional item constraints"""

    def __init__(
        self,
        itemConstraint: Optional[Constraint] = None,
        minLength: Optional[int] = None,
        maxLength: Optional[int] = None,
    ):
        super().__init__(ConstraintType.kList)
        self.itemConstraint = itemConstraint
        self.minLength = minLength
        self.maxLength = maxLength

    def validate(self, value: Any) -> ValidationResult:
        if not isinstance(value, list):
            return ValidationResult(False, "Value must be a list")

        if self.minLength is not None and len(value) < self.minLength:
            return ValidationResult(
                False, f"List must have at least {self.minLength} items"
            )

        if self.maxLength is not None and len(value) > self.maxLength:
            return ValidationResult(
                False, f"List must have at most {self.maxLength} items"
            )

        if self.itemConstraint:
            validated_items = []
            for i, item in enumerate(value):
                result = self.itemConstraint.validate(item)
                if not result.isValid:
                    return ValidationResult(
                        False, f"Item at index {i}: {result.errorMessage}"
                    )
                validated_items.append(result.normalizedValue or item)
            return ValidationResult(True, None, validated_items)

        return ValidationResult(True, None, value)

    def toDict(self) -> Dict[str, Any]:
        return {
            "type": self.constraintType.value,
            "itemConstraint": self.itemConstraint.toDict()
            if self.itemConstraint
            else None,
            "minLength": self.minLength,
            "maxLength": self.maxLength,
        }

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "ListConstraint":
        itemConstraint = None
        if data.get("itemConstraint"):
            itemConstraint = ConstraintFactory.fromDict(data["itemConstraint"])

        return cls(itemConstraint, data.get("minLength"), data.get("maxLength"))


class StringConstraint(Constraint):
    """Constraint for string values"""

    def __init__(
        self,
        minLength: Optional[int] = None,
        maxLength: Optional[int] = None,
        pattern: Optional[str] = None,
    ):
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


class ConstraintFactory:
    """Factory for creating constraints from dictionaries"""

    _constraintClasses = {
        ConstraintType.kRange: RangeConstraint,
        ConstraintType.kListOptions: ListOptionsConstraint,
        ConstraintType.kColor: ColorConstraint,
        ConstraintType.kList: ListConstraint,
        ConstraintType.kString: StringConstraint,
        ConstraintType.kBoolean: BooleanConstraint,
    }

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> Constraint:
        constraintType = ConstraintType(data["type"])
        constraintClass = cls._constraintClasses[constraintType]
        return constraintClass.fromDict(data)


@dataclass
class Setting:
    """A single setting with its constraint and metadata"""

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

    @classmethod
    def fromDict(cls, data: Dict[str, Any]) -> "Setting":
        constraint = ConstraintFactory.fromDict(data["constraint"])
        return cls(
            data["key"],
            constraint,
            data["defaultValue"],
            data.get("description"),
            data.get("category"),
        )


class SettingsAPI:
    """Main settings API for managing settings with constraints"""

    def __init__(self):
        self.settings: Dict[str, Setting] = {}
        self.values: Dict[str, Any] = {}

    def add_setting(self, setting: Setting):
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

    @classmethod
    def deserialize(cls, json_str: str) -> "SettingsAPI":
        """Create SettingsAPI instance from JSON string"""
        data = json.loads(json_str)
        api = cls()

        for key, setting_data in data["settings"].items():
            setting = Setting.fromDict(setting_data)
            api.add_setting(setting)

        api.values = data["values"]
        return api

    def getSettingsSchema(self) -> Dict[str, Any]:
        """Get the schema of all settings (useful for UI generation)"""
        return {key: setting.toDict() for key, setting in self.settings.items()}


class PipelineSettings:
    """Base class for creating pipeline settings collections"""

    PipelineSettingsMapValue = Any

    PipelineSettingsMap = Dict[str, PipelineSettingsMapValue]

    def sendSettings(self, nt_table: NetworkTable):
        """
        Sends the current settings to the specified NetworkTable.

        Args:
            nt_table (NetworkTable): The NetworkTable to send the settings to.
        """
        for key in self.__settings.keys():
            value = self.__settings[key]
            PipelineSettings.setEntryValue(nt_table.getEntry(key), value)

    def get(self, key: str, defaultValue=None) -> Optional[PipelineSettingsMapValue]:
        """
        Retrieves the setting for a given key.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettingsMapValue]: The value of the setting, or None if not found.
        """
        return self.__settings.get(key, defaultValue)

    def set(self, key: str, value: PipelineSettingsMapValue):
        """
        Sets a new value for a given setting key.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettingsMapValue): The value to set for the setting.
        """
        self.__settings[key] = value
        # TODO: Send to NetworkTables, update, and save to file

    def __getitem__(self, key: str):
        """
        Retrieves the setting for a given key using the indexing syntax.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettingsMapValue]: The value of the setting.
        """
        return self.get(key)

    def __setitem__(self, key: str, value: PipelineSettingsMapValue):
        """
        Sets a value for a given setting key using the indexing syntax.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettingsMapValue): The value to set for the setting.
        """
        self.set(key, value)

    def __delitem__(self, key: str):
        """
        Deletes a setting for a given key.

        Args:
            key (str): The key of the setting to delete.
        """
        del self.__settings[key]

    def __str__(self) -> str:
        """
        Returns a string representation of the settings map.

        Returns:
            str: A string representation of the settings.
        """
        return str(self.__settings)

    def __contains__(self, key: Any) -> bool:
        return key in self.__settings.keys()

    def getMap(self) -> PipelineSettingsMap:
        """
        Returns the entire settings map.

        Returns:
            PipelineSettingsMap: The dictionary of settings.
        """
        return self.__settings

    def setMap(self, map: Dict[str, Any]) -> None:
        self.__settings = map

    @staticmethod
    def setEntryValue(entry: NetworkTableEntry, value):
        """
        Sets the value of a NetworkTable entry based on the type of value.

        Args:
            entry (NetworkTableEntry): The NetworkTable entry to set the value for.
            value: The value to set in the entry, which can be an int, float, bool, string, or list.

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

    def __init__(self, settings: Optional[PipelineSettingsMap] = None):
        """
        Initializes the PipelineSettings instance with optional settings.

        Args:
            settings (Optional[PipelineSettingsMap]): A dictionary of settings to initialize with.
        """
        self._settingsApi = SettingsAPI()
        self._fieldNames = []
        self._initializeSettings()

        self.__settings: PipelineSettings.PipelineSettingsMap = (
            settings if settings is not None else {}
        )

    def _initializeSettings(self):
        """Initialize settings based on class annotations and field definitions"""
        for attrName in dir(self.__class__):
            if not attrName.startswith("_"):
                attrValue = getattr(self.__class__, attrName)
                if isinstance(attrValue, Setting):
                    if attrValue.key != attrName:
                        attrValue.key = attrName
                    self._settingsApi.add_setting(attrValue)
                    self._fieldNames.append(attrName)

    def getSetting(self, name: str) -> Any:
        """Get setting value by name"""
        if name in self._fieldNames:
            return self._settingsApi.getValue(name)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no setting '{name}'"
        )

    def setSetting(self, name: str, value: Any):
        """Set setting value by name with validation"""
        if name in self._fieldNames:
            result = self._settingsApi.setValue(name, value)
            if not result.isValid:
                raise ValueError(f"Invalid value for {name}: {result.errorMessage}")
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no setting '{name}'"
            )

    def validate(self, **kwargs) -> Dict[str, ValidationResult]:
        results = {}
        for key, value in kwargs.items():
            if key in self._fieldNames:
                results[key] = self._settingsApi.settings[key].validate(value)
            else:
                results[key] = ValidationResult(False, f"Unknown setting: {key}")
        return results

    def update(self, **kwargs) -> Dict[str, ValidationResult]:
        results = {}
        for key, value in kwargs.items():
            if key in self._fieldNames:
                results[key] = self._settingsApi.setValue(key, value)
            else:
                results[key] = ValidationResult(False, f"Unknown setting: {key}")
        return results

    def toDict(self) -> Dict[str, Any]:
        return {name: self.getSetting(name) for name in self._fieldNames}

    def fromDict(self, data: Dict[str, Any]) -> Dict[str, ValidationResult]:
        return self.update(**data)

    def serialize(self) -> str:
        return self._settingsApi.serialize()

    @classmethod
    def deserialize(cls, jsonStr: str) -> "PipelineSettings":
        instance = cls()
        api = SettingsAPI.deserialize(jsonStr)
        instance._settingsApi = api
        return instance

    def getSchema(self) -> Dict[str, Any]:
        return self._settingsApi.getSettingsSchema()

    def resetToDefaults(self):
        for name in self._fieldNames:
            setting = self._settingsApi.settings[name]
            self._settingsApi.values[name] = setting.defaultValue

    def __repr__(self) -> str:
        values = {name: self.getSetting(name) for name in self._fieldNames}
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in values.items())})"


def settingField(
    constraint: Constraint,
    default: Any,
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> Setting:
    """Helper function to create Setting instances for use in SettingsCollection classes"""
    return Setting("", constraint, default, description, category)
