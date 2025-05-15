from pathlib import Path

from synapse.core import Synapse


def getFilePath() -> Path:
    return Path(__file__).resolve().parent


if __name__ == "__main__":
    Synapse.createAndRunRuntime(root=getFilePath())
