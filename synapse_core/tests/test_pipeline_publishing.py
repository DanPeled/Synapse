# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

from synapse.core.pipeline import Pipeline, PipelineResult, PipelineSettings
from synapse_net.generated.messages.v1 import MessageProto, MessageTypeProto
from synapse_net.socketServer import WebSocketServer


class DummyPipeline(Pipeline[PipelineSettings, PipelineResult]):
    def __init__(self) -> None:
        super().__init__(PipelineSettings())
        self.cameraIndex = 2
        self.pipelineIndex = 3

    def processFrame(self, img, timestamp: float):
        return None


def test_results_are_throttled_to_nt_publish_interval() -> None:
    pipeline = DummyPipeline()

    with (
        patch("synapse.core.pipeline.RESULTS_PUBLISH_INTERVAL", 0.1),
        patch(
            "synapse.core.pipeline.serializePipelineResult", return_value=b"x"
        ) as serialize,
        patch.object(pipeline, "setDataValue") as setDataValue,
    ):
        for _ in range(5):
            pipeline.setResults(object())

        assert serialize.call_count == 1
        assert setDataValue.call_count == 1

        # A "no results" transition must clear stale robot-side data right away.
        pipeline.setResults(None)
        assert setDataValue.call_count == 2
        assert setDataValue.call_args.args == ("results", b"")


def test_result_messages_carry_camera_id_and_coalesce_key() -> None:
    pipeline = DummyPipeline()
    ws = MagicMock()
    ws.hasClients = True

    with patch.object(WebSocketServer, "kInstance", ws):
        pipeline.setDataValue("results", b"\x01", isMsgpack=True)

    message = MessageProto().parse(ws.sendToAllSync.call_args.args[0])
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
