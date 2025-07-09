import { useState } from "react";
import { X, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dropdown } from "@/widgets/dropdown";
import { Column, Row } from "@/widgets/containers";
import { AlertDialog } from "@/widgets/alertDialog";
import TextInput from "@/widgets/textInput";

import { teamColor, borderColor } from "@/services/style";
import { WebSocketWrapper } from "@/services/websocket";

import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";

export function AddPipelineDialog({
  visible,
  setVisible,
  pipelineTypes,
  socket,
  index,
}: {
  visible: boolean;
  setVisible: (state: boolean) => void;
  pipelineTypes: Map<string, PipelineTypeProto>;
  socket?: WebSocketWrapper;
  index: number;
}) {
  const [pipelineType, setPipelineType] = useState<PipelineTypeProto>(
    Array.from(pipelineTypes.values())[0]!,
  );
  const [pipelineName, setPipelineName] = useState("New Pipeline");

  const handleAdd = () => {
    setVisible(false);
    const safeIndex = index === -Infinity ? 0 : index;

    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
      pipelineInfo: PipelineProto.create({
        name: pipelineName,
        type: pipelineType.type,
        index: safeIndex,
        settingsValues: {},
      }),
    });

    const binary = MessageProto.encode(payload).finish();
    socket?.sendBinary(binary);
  };

  return (
    <AlertDialog
      visible={visible}
      onClose={() => setVisible(false)}
      className="w-[40vw] h-[30vh] -translate-y-40"
    >
      <Column gap="gap-2">
        <TextInput
          label="Pipeline Name"
          value={pipelineName}
          onChange={setPipelineName}
          textSize="text-xl"
        />
        <Dropdown
          label="Pipeline Type"
          textSize="text-xl"
          value={pipelineType}
          onValueChange={setPipelineType}
          options={Array.from(pipelineTypes.values()).map((type) => ({
            label: type.type,
            value: type,
          }))}
        />
        <h2 className="text-xl text-center" style={{ color: teamColor }}>
          Pipeline Index: #{index}
        </h2>
      </Column>
      <div className="h-5" />
      <Row gap="gap-2 pt-4 items-center justify-center">
        <Button
          disabled={pipelineName.length === 0}
          variant="outline"
          className="rounded-md bg-zinc-900 hover:bg-zinc-700 text-lg cursor-pointer"
          style={{ borderColor, color: teamColor }}
          onClick={handleAdd}
        >
          <span className="flex items-center gap-2">
            <Check />
            Add Pipeline
          </span>
        </Button>

        <Button
          variant="outline"
          className="rounded-md bg-zinc-900 hover:bg-zinc-700 text-lg cursor-pointer"
          style={{ borderColor, color: teamColor }}
          onClick={() => setVisible(false)}
        >
          <span className="flex items-center gap-2">
            <X />
            Close
          </span>
        </Button>
      </Row>
    </AlertDialog>
  );
}
