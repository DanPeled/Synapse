# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC
from typing import Any, Generic, Optional, Type, TypeVar, Union, overload

import gpiod
from gpiod.line import Direction, Value
from synapse.core.settings_api import (NumberConstraint, Setting,
                                       SettingsCollection, TConstraintType,
                                       settingField)

TPeripheralSettings = TypeVar("TPeripheralSettings", bound=SettingsCollection)
TSettingValueType = TypeVar("TSettingValueType")


class SynapsePeripheral(Generic[TPeripheralSettings], ABC):
    settings: TPeripheralSettings
    name: str

    def __init__(self, name: str, settings: TPeripheralSettings) -> None:
        self.settings = settings
        self.name = name

    @overload
    def getSetting(self, setting: str) -> Optional[Any]: ...

    @overload
    def getSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getSetting(
        self, setting: Union[Setting[TConstraintType, TSettingValueType], str]
    ) -> Optional[Any]:
        return self.settings.getSetting(setting)

    def cleanup(self) -> None:
        """Cleanup method to release resources"""
        pass

    # --- Serialization ---
    def toDict(self) -> dict:
        return {
            "name": self.name,
            "settings": self.settings.toDict(),  # SettingsCollection must implement toDict
        }

    @classmethod
    def fromDict(cls: Type["SynapsePeripheral"], data: dict) -> "SynapsePeripheral":
        settingsCls = cls.__orig_bases__[0].__args__[0]  # type: ignore
        settings = settingsCls.fromDict(data["settings"])
        return cls(data["name"], settings)


class SynapseGpiodPeripheral(SynapsePeripheral[TPeripheralSettings], ABC):
    chipPath: str

    def __init__(self, name: str, settings: TPeripheralSettings, chipPath: str) -> None:
        super().__init__(name, settings)
        self.chipPath = chipPath

    def toDict(self) -> dict:
        base = super().toDict()
        base["chipPath"] = self.chipPath
        base["is_gpio"] = True
        return base

    @classmethod
    def fromDict(
        cls: Type["SynapseGpiodPeripheral"], data: dict
    ) -> "SynapseGpiodPeripheral":
        settingsCls = cls.__orig_bases__[0].__args__[0]  # type: ignore
        settings = settingsCls.fromDict(data["settings"])
        if not data.get("is_gpio", False):
            raise ValueError("Data does not appear to be a GPIO peripheral")
        return cls(data["name"], settings, data["chipPath"])


class LEDPeripheralSettings(SettingsCollection):
    line = settingField(constraint=NumberConstraint(0, None, 1), default=0)


class LEDPeripheral(SynapseGpiodPeripheral[LEDPeripheralSettings]):
    def __init__(
        self, name: str, settings: LEDPeripheralSettings, chipPath: str
    ) -> None:
        super().__init__(name, settings, chipPath)
        lineNumber = self.getSetting("line")
        if lineNumber is None:
            raise ValueError("LED line setting is not configured")
        self._lineNumber = lineNumber
        self._request = gpiod.request_lines(
            chipPath,
            consumer=f"synapse-{self.name}-led",
            config={
                lineNumber: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.INACTIVE
                )
            },
        )

    def on(self) -> None:
        assert self._request is not None
        self._request.set_value(self._lineNumber, Value.ACTIVE)

    def off(self) -> None:
        assert self._request is not None
        self._request.set_value(self._lineNumber, Value.INACTIVE)

    def toggle(self) -> None:
        assert self._request is not None
        current = self._request.get_value(self._lineNumber)
        self._request.set_value(
            self._lineNumber, Value.INACTIVE if current else Value.ACTIVE
        )

    def cleanup(self) -> None:
        if hasattr(self, "_request") and self._request is not None:
            del self._request
            self._request = None


class ButtonPeripheralSettings(SettingsCollection):
    line = settingField(constraint=NumberConstraint(0, None, 1), default=0)


class ButtonPeripheral(SynapseGpiodPeripheral[ButtonPeripheralSettings]):
    def __init__(
        self, name: str, settings: ButtonPeripheralSettings, chipPath: str
    ) -> None:
        super().__init__(name, settings, chipPath)
        lineNumber = int(self.getSetting(self.settings.line))
        if lineNumber is None:
            raise ValueError("Button line setting is not configured")
        self._lineNumber = lineNumber
        self._request = gpiod.request_lines(
            chipPath,
            consumer=f"synapse-{self.name}-button",
            config={
                lineNumber: gpiod.LineSettings(
                    direction=Direction.INPUT, output_value=Value.INACTIVE
                )
            },
        )

    def isPressed(self) -> bool:
        assert self._request is not None
        return self._request.get_value(self._lineNumber) == Value.ACTIVE

    def cleanup(self) -> None:
        if hasattr(self, "_request") and self._request is not None:
            del self._request
            self._request = None
