import os
import re
import sys

import pytest
import synapse.log as log


@pytest.fixture
def cleanupLogs() -> None:
    for f in os.listdir("logs"):
        if f.startswith("logfile_"):
            os.remove(os.path.join("logs", f))


def test_log_creates_file_and_logs_text(cleanupLogs) -> None:
    test_message = "Test log message"
    log.log(test_message)

    log_files = [f for f in os.listdir("logs") if f.startswith("logfile_")]
    assert log_files, "No log files created"

    log_path = os.path.join("logs", log_files[0])
    with open(log_path, "r") as f:
        contents = f.read()
        assert test_message in contents
        assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}]:", contents)


def test_err_logs_error_with_formatting(cleanupLogs) -> None:
    test_error = "Something went wrong"
    log.err(test_error)

    log_files = [f for f in os.listdir("logs") if f.startswith("logfile_")]
    log_path = os.path.join("logs", log_files[0])

    with open(log_path, "r") as f:
        contents = f.read()
        assert "[ERROR]" in contents
        assert test_error in contents

        print(contents)
        assert "\x1b[91m" in contents
        assert "\x1b[0m\n" in contents


def test_stderr_redirection() -> None:
    captured = []

    class CaptureStderr:
        def write(self, data):
            captured.append(data)

    sys_err_backup = sys.stderr
    sys.stderr = CaptureStderr()

    print("Error to stderr", file=sys.stderr)
    sys.stderr = sys_err_backup

    assert any("Error to stderr" in c for c in captured)
