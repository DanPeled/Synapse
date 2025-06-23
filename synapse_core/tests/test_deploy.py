# from pathlib import Path
# from unittest.mock import mock_open, patch
#
# from synapse import deploy
#
#
# @patch("subprocess.run")
# def test_check_python3_install_success(mock_run):
#     mock_run.return_value.returncode = 0
#     assert deploy.check_python3_install()
#
#
# @patch("subprocess.run", side_effect=FileNotFoundError)
# def test_check_python3_install_not_found(mock_run):
#     assert not (deploy.check_python3_install())
#
#
# @patch("builtins.open", new_callable=mock_open, read_data="*.pyc\n")
# @patch("os.path.exists", return_value=True)
# def test_get_gitignore_specs_exists(mock_exists, mock_file):
#     spec = deploy.get_gitignore_specs(Path(__file__).parent)
#
#     assert spec.match_file("test.pyc")
#
#
# @patch("os.path.exists", return_value=False)
# def test_get_gitignore_specs_missing(mock_exists):
#     spec = deploy.get_gitignore_specs(Path(__file__).parent)
#     assert not (spec.match_file("test.py"))
#
#
# @patch("subprocess.run")
# def test_compile_file_success(mock_run):
#     mock_run.return_value.returncode = 0
#     assert deploy.compile_file("file.py")
#
#
# @patch("subprocess.run")
# def test_compile_file_failure(mock_run):
#     mock_run.return_value.returncode = 1
#     mock_run.return_value.stderr = b"Syntax error"
#     assert not (deploy.compile_file("bad_file.py"))
