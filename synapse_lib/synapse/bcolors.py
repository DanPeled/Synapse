from typing import Final


class bcolors:
    """
    ANSI escape sequences for coloring terminal text output.

    These constants can be used to format strings with different colors and styles
    when printed to a terminal that supports ANSI escape codes.
    """

    HEADER: Final[str] = "\033[95m"  # Light magenta
    OKBLUE: Final[str] = "\033[94m"  # Light blue
    OKCYAN: Final[str] = "\033[96m"  # Light cyan
    OKGREEN: Final[str] = "\033[92m"  # Light green
    WARNING: Final[str] = "\033[93m"  # Yellow (typically used for warnings)
    FAIL: Final[str] = "\033[91m"  # Light red (typically used for errors)
    ENDC: Final[str] = "\033[0m"  # Reset to default color
    BOLD: Final[str] = "\033[1m"  # Bold text
    UNDERLINE: Final[str] = "\033[4m"  # Underlined text
