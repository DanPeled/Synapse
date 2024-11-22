import datetime
import os
from typing_extensions import Any

PRINTS = True

# Create a logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Generate a new log file name based on the current date and time
LOG_FILE = f"logs/logfile_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"


def log(text: Any):
    # Get the current time
    current_time = datetime.datetime.now()

    # Format the time in a human-readable way
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    final_string = f"[{formatted_time}]: {text}"

    if PRINTS:
        print(str(final_string))

    # Write the log to the new file
    with open(LOG_FILE, "a") as f:
        f.write(str(final_string) + "\n")
