# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Callable, cast
from unittest.mock import MagicMock, patch

from synapse.core.pipeline import Pipeline, PipelineResult, PipelineSettings
from synapse.core.settings_api import CameraSettings
from synapse_net.generated.messages.v1 import MessageProto, MessageTypeProto
from synapse_net.socketServer import WebSocketServer


class DummyPipeline(Pipeline[PipelineSettings, PipelineResult]):
    def __init__(self) -> None:
        super().__init__(PipelineSettings())
        self.cameraIndex = 2
        self.pipelineIndex = 3

    def processFrame(self, img, timestamp: float):
        return None


def test_results_are_published_immediately() -> None:
    pipeline = DummyPipeline()

    with (
        patch(
            "synapse.core.pipeline.serializePipelineResult", return_value=b"x"
        ) as serialize,
        patch.object(pipeline, "setDataValue") as setDataValue,
    ):
        for _ in range(5):
            pipeline.setResults(PipelineResult())

        assert serialize.call_count == 5
        assert setDataValue.call_count == 5

        # A "no results" transition clears stale robot-side data too.
        pipeline.setResults(None)
        assert setDataValue.call_count == 6
        assert setDataValue.call_args.args == ("results", b"")


def test_result_messages_carry_camera_id_and_coalesce_key() -> None:
    pipeline = DummyPipeline()
    ws = MagicMock()
    ws.hasClients = True

    with patch.object(WebSocketServer, "kInstance", ws):
        pipeline.setDataValue("results", b"\x01", isMsgpack=True)

    payload = ws.sendToAllSync.call_args.args[0]
    assert callable(payload)
    message = MessageProto().parse(cast(Callable[[], bytes], payload)())
    result = message.pipeline_result

    assert result.cameraid == 2
    assert result.pipeline_index == 3
    assert result.key == "results"
    assert result.is_msgpack is True
    assert ws.sendToAllSync.call_args.kwargs["coalesce_key"] == (
        MessageTypeProto.SET_PIPELINE_RESULT,
        2,
        3,
        "results",
    )


def test_websocket_message_is_built_lazily() -> None:
    pipeline = DummyPipeline()
    ws = MagicMock()
    ws.hasClients = True

    with (
        patch.object(WebSocketServer, "kInstance", ws),
        patch("synapse.core.pipeline.createMessage", return_value=b"encoded") as build,
    ):
        pipeline.setDataValue("results", b"\x01", isMsgpack=True)
        build.assert_not_called()

        payload = ws.sendToAllSync.call_args.args[0]
        assert callable(payload)
        assert cast(Callable[[], bytes], payload)() == b"encoded"
        build.assert_called_once()


def test_no_websocket_message_is_built_without_clients() -> None:
    pipeline = DummyPipeline()
    ws = MagicMock()
    ws.hasClients = False

    with (
        patch.object(WebSocketServer, "kInstance", ws),
        patch("synapse.core.pipeline.createMessage") as createMessage,
    ):
        pipeline.setDataValue("results", b"\x01", isMsgpack=True)

    createMessage.assert_not_called()
    ws.sendToAllSync.assert_not_called()


def test_resolution_parsing_is_cached_until_the_setting_changes() -> None:
    pipeline = DummyPipeline()

    assert pipeline.getResolution() == (1920, 1080)
    cached = pipeline._resolutionCache
    assert pipeline.getResolution() == (1920, 1080)
    assert pipeline._resolutionCache is cached

    pipeline.setCameraSetting(CameraSettings.resolution, "640x480")

    assert pipeline.getResolution() == (640, 480)
    assert pipeline._resolutionCache is not cached
