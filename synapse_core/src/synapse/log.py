# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import atexit
import datetime
import os
import time
from collections import deque
from typing import Any, Optional

import synapse_net.generated.messages.v1 as v1
from rich import print
from synapse_net.socketServer import WebSocketServer, createMessage

from .alert import alert
from .bcolors import MarkupColors, TextTarget, parseTextStyle

# Flag to control printing to the console
PRINTS = True

# Create a logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Generate a new log file name based on the current date and time
LOG_FILE = f"logs/logfile_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
LOG_HANDLE = open(LOG_FILE, "a", buffering=1)

atexit.register(LOG_HANDLE.close)


class ErrorWriter(object):
    def write(self, data: Any):
        print(MarkupColors.fail(data), end="")


# sys.stderr = ErrorWriter()

logs = deque(maxlen=1000)


def socketLog(
    text: str, msgType: v1.LogLevelProto, socket: Optional[WebSocketServer]
) -> None:
    logs.append(
        v1.LogMessageProto(
            message=text, level=msgType, timestamp=int(time.time() * 1_000)
        )
    )

    if socket is not None:
        msg = createMessage(v1.MessageTypeProto.LOG, logs[-1])

        socket.sendToAllSync(msg)


def addTime(text: str) -> str:
    # Get the current time
    current_time = datetime.datetime.now()

    # Format the time in a human-readable way
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    final_string = f"[{formatted_time}]: {text}"
    return final_string


def logInternal(text: str):
    if PRINTS:
        print(text)

    LOG_HANDLE.write(text + "\n")
    LOG_HANDLE.flush()


def info(text: str, shouldAlert=False):
    modifiedtext = addTime(text)
    logInternal(modifiedtext)
    socketLog(modifiedtext, v1.LogLevelProto.INFO, WebSocketServer.kInstance)
    if shouldAlert:
        alert(v1.AlertTypeProto.INFO, text)


def err(text: str):
    """
    Logs an error message with the current timestamp by prepending '[ERROR]' to the message.

    Args:
        text (str): The error message to log.

    This function calls the `log` function and formats the message to indicate an error.
    """
    text = MarkupColors.fail(f"[ERROR]: {text}")
    text = addTime(text)
    logInternal(parseTextStyle(MarkupColors.fail(text)))
    socketLog(
        parseTextStyle(text, target=TextTarget.kHTML),
        v1.LogLevelProto.ERROR,
        WebSocketServer.kInstance,
    )

    alert(v1.AlertTypeProto.ERROR, text)


def warn(text: str):
    """
    Logs a warning message with the current timestamp by prepending '[WARNING]' to the message.

    Args:
        text (str): The warning message to log.

    This function calls the `log` function and formats the message to indicate an warning.
    """
    text = MarkupColors.warning(f"[WARNING]: {text}")
    text = addTime(text)
    logInternal(parseTextStyle(text))
    socketLog(
        text,
        v1.LogLevelProto.WARNING,
        WebSocketServer.kInstance,
    )

    alert(v1.AlertTypeProto.WARNING, text)


def missingFeature(text: str) -> None:
    err(
        f"{text}\nIf you'd like to see this feature added, feel free to open an issue on GitHub — or even better, contribute by submitting a pull request!\nGitHub repo: https://github.com/DanPeled/Synapse"
    )
