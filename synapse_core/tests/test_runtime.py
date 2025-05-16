from pathlib import Path
from unittest.mock import MagicMock
from synapse.core import Synapse
from synapse.core.pipeline_handler import PipelineHandler


def test_synapse_run_called_when_init_succeeds():
    root = Path(__file__).parent
    handler = PipelineHandler(root)
    s = Synapse()

    s.init = MagicMock(return_value=True)
    s.run = MagicMock()

    if s.init(handler, root / "config" / "settings.yml"):
        s.run()

    s.run.assert_called_once()


def test_synapse_run_not_called_when_init_fails():
    root = Path(__file__).parent
    handler = PipelineHandler(root)
    s = Synapse()

    s.run = MagicMock()

    if s.init(handler, root / "config" / "fake.yml"):
        s.run()

    s.run.assert_not_called()
