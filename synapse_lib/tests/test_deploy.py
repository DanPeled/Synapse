import os
import sys
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import deploy


class TestDeployScript(unittest.TestCase):
    @patch("subprocess.run")
    def test_check_python3_install_success(self, mock_run):
        mock_run.return_value.returncode = 0
        self.assertTrue(deploy.check_python3_install())

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_check_python3_install_not_found(self, mock_run):
        self.assertFalse(deploy.check_python3_install())

    @patch("builtins.open", new_callable=mock_open, read_data="*.pyc\n")
    @patch("os.path.exists", return_value=True)
    def test_get_gitignore_specs_exists(self, mock_exists, mock_file):
        spec = deploy.get_gitignore_specs()
        self.assertTrue(spec.match_file("test.pyc"))

    @patch("os.path.exists", return_value=False)
    def test_get_gitignore_specs_missing(self, mock_exists):
        spec = deploy.get_gitignore_specs()
        self.assertFalse(spec.match_file("test.py"))

    @patch("subprocess.run")
    def test_compile_file_success(self, mock_run):
        mock_run.return_value.returncode = 0
        self.assertTrue(deploy.compile_file("file.py"))

    @patch("subprocess.run")
    def test_compile_file_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = b"Syntax error"
        self.assertFalse(deploy.compile_file("bad_file.py"))

    @patch("deploy.compile_file", return_value=True)
    @patch("os.walk", return_value=[(".", [], ["file1.py", "file2.py"])])
    def test_build_project_success(self, mock_walk, mock_compile):
        result, duration = deploy.build_project()
        self.assertTrue(result)
        self.assertIsInstance(duration, timedelta)

    @patch("deploy.compile_file", return_value=False)
    @patch("os.walk", return_value=[(".", [], ["file1.py"])])
    def test_build_project_failure(self, mock_walk, mock_compile):
        result, _ = deploy.build_project()
        self.assertFalse(result)

    @patch("paramiko.SSHClient")
    @patch("tarfile.open")
    def test_deploy_success(self, mock_tar, mock_ssh_client):
        ssh_instance = MagicMock()
        mock_ssh_client.return_value = ssh_instance
        sftp = ssh_instance.open_sftp.return_value
        stdout = MagicMock()
        stdout.read.return_value = b"Restarted"
        stderr = MagicMock()
        stderr.read.return_value = b""

        ssh_instance.exec_command.side_effect = [
            (None, stdout, stderr),
            (None, stdout, stderr),
            (None, stdout, stderr),
            (None, stdout, stderr),
        ]

        with patch.dict(
            "deploy.__dict__",
            {
                "hostname": "localhost",
                "port": 22,
                "username": "user",
                "password": "pass",
                "remote_path": "~/path/",
                "tarball_path": "/tmp/deploy.tar.gz",
            },
        ):
            deploy.deploy()

        ssh_instance.connect.assert_called_once()
        ssh_instance.exec_command.assert_any_call(
            "echo 'pass' | sudo -S systemctl restart synapse"
        )
        sftp.put.assert_called_once()


if __name__ == "__main__":
    unittest.main()
