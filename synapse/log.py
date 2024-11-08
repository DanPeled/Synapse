import datetime

PRINTS = True
LOG_FILE = "logfile.log"


def log(text: str):
    # Get the current time
    current_time = datetime.datetime.now()

    # Format the time in a human-readable way
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    final_string = f"[{formatted_time}]: {text}"
    if PRINTS:
        print(final_string)
    with open(LOG_FILE, "a") as f:
        f.write(final_string + "\n")
