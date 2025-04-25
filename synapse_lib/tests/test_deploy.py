import os
import sys
import unittest
from unittest.mock import mock_open, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from synapse import deploy


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


if __name__ == "__main__":
    unittest.main()
