import pytest
from unittest.mock import patch, MagicMock
from hardware import (
    MetricsManager,
    Platform,
    LinuxCmds,
)
import json


# Test for MetricsManager initialization
@pytest.fixture
def metrics_manager():
    return MetricsManager()


# Test for setting the configuration
@patch("hardware.metrics.Platform.isLinux", return_value=True)
def test_set_config_linux(mock_is_linux, metrics_manager):
    metrics_manager.setConfig(None)
    assert isinstance(metrics_manager.cmds, LinuxCmds)


# Test for platform detection
@patch("hardware.metrics.Platform.getCurrentPlatform", return_value=Platform.LINUX_64)
def test_get_platform_name(mock_get_current_platform):
    platform_name = Platform.getPlatformName()
    assert platform_name == "Linux x64"


def test_get_memory(metrics_manager):
    metrics_manager.setConfig(None)
    result = metrics_manager.getMemory()
    assert result == "7676"


# Test for safe execute when command fails
@patch.object(MetricsManager, "execute", side_effect=Exception("Command failed"))
def test_safe_execute_failure(mock_execute, metrics_manager):
    result = metrics_manager.safeExecute("some_command")
    assert result == "****"


# Test for getting temperature with valid command
@patch.object(MetricsManager, "safeExecute", return_value="45")
def test_get_temp(mock_safe_execute, metrics_manager):
    metrics_manager.setConfig(None)
    result = metrics_manager.getTemp()
    assert result == "45"


# Test for getUtilization when no command is set
def test_get_utilization_no_command(metrics_manager):
    metrics_manager.cmds = None
    result = metrics_manager.getUtilization()
    assert result == ""


# Test for safe execute when command is valid
@patch.object(MetricsManager, "execute", return_value="Command success")
def test_safe_execute_valid(mock_execute, metrics_manager):
    result = metrics_manager.safeExecute("valid_command")
    assert result == "Command success"


# Test for platform-specific behavior
@patch("hardware.metrics.Platform.isRaspberryPi", return_value=True)
def test_get_temp_raspberry_pi(mock_is_raspberry_pi, metrics_manager):
    metrics_manager.setConfig(None)
    result = metrics_manager.getTemp()
    assert result == "20.000"
