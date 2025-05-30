import os
from pathlib import Path

from synapse.core import Synapse


def main():
    Synapse.createAndRunRuntime(root=Path(os.getcwd()))


if __name__ == "__main__":
    main()
