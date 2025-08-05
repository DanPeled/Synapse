import io
import unittest
from unittest.mock import MagicMock, mock_open, patch

import synapse_installer.sync as deploy_sync


class TestSyncRequirements(unittest.TestCase):
    @patch("paramiko.SSHClient")
    @patch("synapse_installer.sync.log.err")
    @patch("synapse_installer.sync.fprint")
    def test_sync_requirements_installs_missing_packages(
        self, mock_fprint, mock_log_err, mock_ssh_client
    ):
        # Setup mock SSHClient and transport
        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport

        # Simulate installed packages output - only package 'foo' installed
        installed_packages_output = "foo==1.0.0\n"
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = installed_packages_output.encode()
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        # First exec_command: sudoers setup (no error)
        mock_client.exec_command.side_effect = [
            (MagicMock(), MagicMock(), mock_stderr),  # sudoers setup
            (MagicMock(), mock_stdout, mock_stderr),  # pip freeze
            # install command for package 'bar'
            (MagicMock(), MagicMock(), MagicMock()),
        ]

        # Requirements: 'foo' (already installed), 'bar' (missing)
        requirements = ["foo>=1.0", "bar==2.0"]

        deploy_sync.syncRequirements("host", "pass", "1.2.3.4", requirements)

        # Check that fprint was called with installing message for 'bar'
        calls = [call.args[0] for call in mock_fprint.call_args_list]
        self.assertTrue(any("Installing bar" in c for c in calls))

    @patch("paramiko.SSHClient")
    @patch("synapse_installer.sync.log.err")
    def test_sync_requirements_ssh_exception_logs_error(
        self, mock_log_err, mock_ssh_client
    ):
        mock_ssh_client.side_effect = Exception("SSH failure")
        deploy_sync.syncRequirements("host", "pass", "1.2.3.4", ["foo"])
        mock_log_err.assert_called()
        self.assertIn("SSH failure", mock_log_err.call_args[0][0])


class TestSync(unittest.TestCase):
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="deploy:\n  device1:\n    hostname: host1\n    password: pass1\n    ip: 1.2.3.4\n",
    )
    @patch("synapse_installer.sync.Path.exists", return_value=True)
    @patch("synapse_installer.sync.addDeviceConfig")
    @patch("synapse_installer.sync.distribution")
    @patch("synapse_installer.sync.syncRequirements")
    @patch("synapse_installer.sync.fprint")
    def test_sync_calls_syncRequirements_with_deploy(
        self,
        mock_fprint,
        mock_sync_req,
        mock_dist,
        mock_add_config,
        mock_path_exists,
        mock_file,
    ):
        # Setup distribution requires
        mock_dist.return_value.requires = ["pkg1", "pkg2"]

        argv = ["scriptname", "device1"]

        deploy_sync.sync(argv)

        mock_sync_req.assert_called_once_with(
            "host1", "pass1", "1.2.3.4", ["pkg1", "pkg2"]
        )

    @patch("synapse_installer.sync.Path.exists", return_value=False)
    def test_sync_no_synapseproject_file_raises_assertion(self, mock_path_exists):
        with self.assertRaises(AssertionError):
            deploy_sync.sync(["device1"])

    @patch("builtins.open", new_callable=mock_open, read_data="deploy: {}\n")
    @patch("synapse_installer.sync.Path.exists", return_value=True)
    @patch("synapse_installer.sync.addDeviceConfig")
    @patch("synapse_installer.sync.fprint")
    def test_sync_adds_device_config_if_deploy_missing(
        self, mock_fprint, mock_add_config, mock_path_exists, mock_file
    ):
        argv = ["scriptname", "device1"]
        # Simulate no 'deploy' in data on first read, then deploy added on second read
        # mock_open cannot do multiple returns easily, so patch open to simulate this
        data_with_no_deploy = ""
        data_with_deploy = "deploy:\n  device1:\n    hostname: host1\n    password: pass1\n    ip: 1.2.3.4\n"

        def open_side_effect(file, mode="r", *args, **kwargs):
            if open_side_effect.counter == 0:
                open_side_effect.counter += 1
                file_object = io.StringIO(data_with_no_deploy)
                return file_object
            else:
                return io.StringIO(data_with_deploy)

        open_side_effect.counter = 0

        with patch("builtins.open", side_effect=open_side_effect):
            with patch("synapse_installer.sync.distribution") as mock_dist:
                with patch("synapse_installer.sync.syncRequirements") as mock_sync_req:
                    mock_dist.return_value.requires = ["pkg1"]
                    deploy_sync.sync(argv)
                    mock_add_config.assert_called_once()
                    mock_sync_req.assert_called_once_with(
                        "host1", "pass1", "1.2.3.4", ["pkg1"]
                    )

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="deploy:\n  device2:\n    hostname: host2\n    password: pass2\n    ip: 2.3.4.5\n",
    )
    @patch("synapse_installer.sync.Path.exists", return_value=True)
    @patch("synapse_installer.sync.fprint")
    def test_sync_hostname_not_in_deploy(
        self, mock_fprint, mock_path_exists, mock_file
    ):
        argv = ["scriptname", "unknown_device"]
        deploy_sync.sync(argv)
        mock_fprint.assert_called()
        self.assertIn(
            "No device named: `unknown_device` found! skipping...",
            mock_fprint.call_args[0][0],
        )


if __name__ == "__main__":
    unittest.main()
