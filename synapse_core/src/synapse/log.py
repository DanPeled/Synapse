import datetime
import os
import sys

from synapse.bcolors import bcolors

# Flag to control printing to the console
PRINTS = True

# Create a logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Generate a new log file name based on the current date and time
LOG_FILE = f"logs/logfile_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"


class writer(object):
    def write(self, data):
        print(f"{bcolors.FAIL}{data}{bcolors.ENDC}", end="")


sys.stderr = writer()


def log(text: str):
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


def err(text: str):
    """
    Logs an error message with the current timestamp by prepending '[ERROR]' to the message.

    Args:
        text (str): The error message to log.

    This function calls the `log` function and formats the message to indicate an error.
    """
    log(bcolors.FAIL + f"[ERROR]: {text}" + bcolors.ENDC)


def warn(text: str):
    """
    Logs a warning message with the current timestamp by prepending '[WARNING]' to the message.

    Args:
        text (str): The warning message to log.

    This function calls the `log` function and formats the message to indicate an warning.
    """
    log(bcolors.WARNING + f"[WARNING]: {text}" + bcolors.ENDC)
