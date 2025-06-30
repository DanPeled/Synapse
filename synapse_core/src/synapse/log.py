import datetime
import os
from enum import Enum
from typing import Any, Optional

from rich import print
from synapse_net.socketServer import WebSocketServer

from .bcolors import MarkupColors, TextTarget, parseTextStyle

# Flag to control printing to the console
PRINTS = True

# Create a logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Generate a new log file name based on the current date and time
LOG_FILE = f"logs/logfile_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"


class ErrorWriter(object):
    def write(self, data: Any):
        print(MarkupColors.fail(data), end="")


# sys.stderr = ErrorWriter()


class LogMessageType(Enum):
    INFO = "info"
    ERR = "error"
    WARN = "warning"


def socketLog(
    text: str, msgType: LogMessageType, socket: Optional[WebSocketServer]
) -> None:
    ...
    # if socket:
    #     socket.sendToAllSync(
    #         createMessageFromDict("log", {"message": text, "type": msgType.value})
    #     )


def logInternal(text: str):
    """
    Logs a message with the current timestamp to both the console and a log file.

    Args:
        text (str): The message to log.

    Writes:
        - The log message to the console.
        - The log message to the log file `logs/logfile_<timestamp>.log`.
    """
    # Get the current time
    current_time = datetime.datetime.now()

    # Format the time in a human-readable way
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    final_string = f"[{formatted_time}]: {text}"

    # Print the log message to the console if PRINTS is True
    if PRINTS:
        print(text)

    # Write the log to the new file
    with open(LOG_FILE, "a") as f:
        f.write(str(final_string) + "\n")


def log(text: str):
    logInternal(text)
    socketLog(text, LogMessageType.INFO, WebSocketServer.kInstance)


def err(text: str):
    """
    Logs an error message with the current timestamp by prepending '[ERROR]' to the message.

    Args:
        text (str): The error message to log.

    This function calls the `log` function and formats the message to indicate an error.
    """
    text = MarkupColors.fail(f"[ERROR]: {text}")
    logInternal(parseTextStyle(MarkupColors.fail(text)))
    socketLog(
        parseTextStyle(text, target=TextTarget.kHTML),
        LogMessageType.ERR,
        WebSocketServer.kInstance,
    )


def warn(text: str):
    """
    Logs a warning message with the current timestamp by prepending '[WARNING]' to the message.

    Args:
        text (str): The warning message to log.

    This function calls the `log` function and formats the message to indicate an warning.
    """
    text = MarkupColors.warning(f"[WARNING]: {text}")
    logInternal(parseTextStyle(text))
    socketLog(
        parseTextStyle(text, TextTarget.kHTML),
        LogMessageType.WARN,
        WebSocketServer.kInstance,
    )
