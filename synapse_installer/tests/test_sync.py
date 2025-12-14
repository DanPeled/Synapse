# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from synapse_installer.command_executor import SSHCommandExecutor
from synapse_installer.sync import (installPipRequirements,
                                    installSystemPackage, setupSudoers,
                                    syncRequirements)


@pytest.fixture
def mockExecutor(mocker):
    """Create a mock command executor."""
    executor = mocker.Mock()
    # default execCommand returns success
    executor.execCommand.return_value = ("", "", 0)
    return executor


class TestSetupSudoers:
    """Tests for setupSudoers function."""

    def test_setup_sudoers_success(self, mockExecutor, mocker):
        mocker.patch("synapse_installer.sync.fprint")
        mockExecutor.execCommand.return_value = ("", "", 0)

        setupSudoers(mockExecutor, "robot", "root", "")

        mockExecutor.execCommand.assert_called_once()

    def test_setup_sudoers_failure(self, mockExecutor, mocker):
        fprintMock = mocker.patch("synapse_installer.sync.fprint")
        mockExecutor.execCommand.return_value = ("", "error", 1)

        setupSudoers(mockExecutor, "robot", "root", "")

        fprintMock.assert_called_once()
        assert "Failed to setup sudoers" in str(fprintMock.call_args)


class TestInstallSystemPackage:
    """Tests for installSystemPackage function."""

    def test_install_system_package_already_installed(self, mockExecutor):
        # checkCmd returns 0 -> package already installed
        mockExecutor.execCommand.side_effect = [
            ("", "", 0),  # manager exists
            ("", "", 0),  # package check
        ]

        installSystemPackage(mockExecutor, "git")

        assert mockExecutor.execCommand.call_count == 2

    def test_install_system_package_needs_install(self, mockExecutor):
        # checkCmd returns non-zero -> needs install
        mockExecutor.execCommand.side_effect = [
            ("", "", 0),  # manager exists
            ("", "", 1),  # package check fails
            ("", "", 0),  # install command
        ]

        installSystemPackage(mockExecutor, "git")

        assert mockExecutor.execCommand.call_count == 3

    def test_install_system_package_no_manager(self, mockExecutor):
        # No package manager exists
        mockExecutor.execCommand.return_value = ("", "", 1)

        with pytest.raises(RuntimeError):
            installSystemPackage(mockExecutor, "git")


class TestInstallPipRequirements:
    """Tests for installPipRequirements function."""

    def test_all_installed(self, mockExecutor, mocker):
        mockExecutor.execCommand.return_value = (
            "numpy==1.21.0\npandas==1.3.0\n",
            "",
            0,
        )
        fprintMock = mocker.patch("synapse_installer.sync.fprint")

        installPipRequirements(
            mockExecutor, ["numpy==1.21.0", "pandas==1.3.0"], "python3"
        )

        # Should print OK for each package
        assert fprintMock.call_count == 2
        assert "[OK]" in str(fprintMock.call_args_list[0])

    def test_partial_installed(self, mockExecutor, mocker):
        mockExecutor.execCommand.side_effect = [
            ("numpy==1.21.0\n", "", 0),  # pip freeze
            ("", "", 0),  # pip install pandas
        ]
        fprintMock = mocker.patch("synapse_installer.sync.fprint")

        installPipRequirements(
            mockExecutor, ["numpy==1.21.0", "pandas==1.3.0"], "python3"
        )

        # numpy should be OK, pandas installed
        calls = [str(c) for c in fprintMock.call_args_list]
        assert any("already installed" in c for c in calls)
        assert any("Installing pandas" in c for c in calls)

    def test_none_installed(self, mockExecutor, mocker):
        mockExecutor.execCommand.side_effect = [
            ("", "", 0),  # pip freeze empty
            ("", "", 0),  # pip install numpy
            ("", "", 0),  # pip install pandas
        ]
        fprintMock = mocker.patch("synapse_installer.sync.fprint")

        installPipRequirements(
            mockExecutor, ["numpy==1.21.0", "pandas==1.3.0"], "python3"
        )

        calls = [str(c) for c in fprintMock.call_args_list]
        assert all("Installing" in c for c in calls)


class TestSyncRequirements:
    """Tests for syncRequirements function."""

    def test_local_executor(self, mocker):
        from synapse_installer.command_executor import LocalCommandExecutor

        executor = mocker.Mock(spec=LocalCommandExecutor)
        executor.execCommand.return_value = ("", "", 0)
        _ = mocker.patch("synapse_installer.sync.fprint")
        mocker.patch("synapse_installer.sync.setupSudoers")
        mocker.patch("synapse_installer.sync.installSystemPackage")
        mocker.patch("synapse_installer.sync.installPipRequirements")

        syncRequirements(executor, "localhost", "localhost", "", ["numpy"])

        executor.close.assert_called_once()

    def test_remote_executor(self, mocker):
        executor = mocker.Mock(spec=SSHCommandExecutor)
        executor.execCommand.return_value = ("", "", 0)
        _ = mocker.patch("synapse_installer.sync.fprint")
        mocker.patch("synapse_installer.sync.setupSudoers")
        mocker.patch("synapse_installer.sync.installSystemPackage")
        mocker.patch("synapse_installer.sync.installPipRequirements")

        syncRequirements(executor, "remotehost", "remotehost", "", ["numpy"])

        executor.close.assert_called_once()
