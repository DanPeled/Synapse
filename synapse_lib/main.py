from pathlib import Path
from synapse.core import PipelineHandler, Synapse


def getFilePath() -> Path:
    return Path(__file__).resolve().parent


if __name__ == "__main__":
    handler = PipelineHandler(getFilePath())
    s = Synapse()
    if s.init(handler, getFilePath() / "config" / "settings.yml"):
        s.run()
