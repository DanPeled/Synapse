# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Dict, Optional, Type

import yaml

from ._peripherals import ButtonPeripheral, LEDPeripheral, SynapsePeripheral


class SynapsePeripheralManager:
    peripheralTypes: Dict[str, Type[SynapsePeripheral]] = {
        "led": LEDPeripheral,
        "button": ButtonPeripheral,
    }

    def __init__(self) -> None:
        self.peripherals: Dict[str, SynapsePeripheral] = {}

    def addPeripheral(
        self, name: str, peripheral: SynapsePeripheral, replace: bool = False
    ) -> None:
        if not replace and name in self.peripherals:
            raise KeyError(f"Peripheral '{name}' already exists.")
        self.peripherals[name] = peripheral

    def getPeripheral(self, name: str) -> Optional[SynapsePeripheral]:
        return self.peripherals.get(name)

    def removePeripheral(self, name: str, cleanup: bool = True) -> None:
        peripheral = self.peripherals.pop(name, None)
        if peripheral and cleanup:
            self.cleanupPeripheral(peripheral)

    def clearPeripherals(self, cleanup: bool = True) -> None:
        if cleanup:
            for peripheral in self.peripherals.values():
                self.cleanupPeripheral(peripheral)
        self.peripherals.clear()

    def listPeripherals(self) -> Dict[str, SynapsePeripheral]:
        return self.peripherals.copy()

    @staticmethod
    def cleanupPeripheral(peripheral: SynapsePeripheral) -> None:
        peripheral.cleanup()

    # --- Save / Load ---
    def saveToFile(self, filePath: Path | str) -> None:
        """
        Save all peripherals to a yaml file.
        Each peripheral must implement a `toDict()` method.
        """
        data = {}
        for name, peripheral in self.peripherals.items():
            peripheralType = None
            for key, cls in self.peripheralTypes.items():
                if isinstance(peripheral, cls):
                    peripheralType = key
                    break
            if peripheralType is None:
                raise ValueError(f"Unknown peripheral type for {name}")
            data[name] = {"type": peripheralType, "data": peripheral.toDict()}
        with open(filePath, "w") as f:
            yaml.dump(data, f, indent=4)

    def loadFromFile(self, filePath: Path | str, replace: bool = False) -> None:
        """
        Load peripherals from a yaml file.
        Automatically cleans up existing peripherals if replacing.
        """
        with open(filePath, "r") as f:
            data = yaml.full_load(f)
        for name, info in data.items():
            peripheralType = info["type"]
            peripheralData = info["data"]
            cls = self.peripheralTypes.get(peripheralType)
            if cls is None:
                raise ValueError(f"Unknown peripheral type '{peripheralType}' in file")

            # Cleanup if replacing
            if replace and name in self.peripherals:
                self.cleanupPeripheral(self.peripherals[name])

            peripheral = cls.fromDict(peripheralData)
            self.addPeripheral(name, peripheral, replace=replace)
