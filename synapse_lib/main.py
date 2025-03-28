from core import Synapse, PipelineHandler
from pathlib import Path


def getFilePath() -> Path:
    return Path(__file__).resolve().parent


if __name__ == "__main__":
    handler = PipelineHandler(getFilePath() / "pipelines")
    s = Synapse()
    if s.init(handler):
        s.run()
