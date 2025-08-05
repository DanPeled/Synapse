import os
import subprocess
import sys

from ..log import err, log, missingFeature
from .metrics import Platform


def reboot():
    if Platform.getCurrentPlatform().isLinux():
        try:
            subprocess.run(["reboot"], check=True)
        except subprocess.CalledProcessError as e:
            err(f"Failed to reboot: {e}")
    else:
        missingFeature("Rebooting is not yet supported on non-Linux systems.")


def restartRuntime():
    log("Restarting Synapse...")
    os.execv(sys.executable, [sys.executable] + sys.argv)
