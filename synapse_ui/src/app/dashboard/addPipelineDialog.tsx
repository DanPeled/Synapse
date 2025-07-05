import { useState } from "react";
import { Button } from "@/components/ui/button";
import { X, Check } from "lucide-react";
import { teamColor, borderColor } from "@/services/style";
import { Dropdown } from "@/widgets/dropdown";
import { Column, Row } from "@/widgets/containers";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { AlertDialog } from "@/widgets/alertDialog";
import TextInput from "@/widgets/textInput";
import { WebSocketWrapper } from "@/services/websocket";
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
    Array.from(pipelineTypes.values()).at(0)!,
  );
  const [pipelineName, setPipelineName] = useState("New Pipeline");

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
          onChange={(val) => setPipelineName(val)}
          textSize="text-xl"
        />
        <Dropdown
          textSize="text-xl"
          label="Pipeline Type"
          value={pipelineType}
          onValueChange={(val) => {
            setPipelineType(val);
          }}
          options={Array.from(pipelineTypes.entries()).map(([_, type]) => ({
            label: type.type,
            value: type,
          }))}
        />
      </Column>
      <Row gap="gap-2 pt-4 items-center justify-center">
        <Button
          disabled={pipelineName.length === 0}
          variant="outline"
          className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
          style={{
            borderColor: borderColor,
            color: teamColor,
          }}
          onClick={() => {
            setVisible(false);
            const payload = MessageProto.create({
              type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
              pipelineInfo: PipelineProto.create({
                name: pipelineName,
                type: pipelineType.type,
                index: index,
                settingsValues: {},
              }),
            });

            const binary = MessageProto.encode(payload).finish();
            socket?.sendBinary(binary);
          }}
        >
          <span className="flex items-center justify-center gap-2 text-lg">
            <Check />
            Confirm
          </span>
        </Button>
        <Button
          variant="outline"
          className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700 text-lg"
          style={{
            borderColor: borderColor,
            color: teamColor,
          }}
          onClick={() => setVisible(false)}
        >
          <span className="flex items-center justify-center gap-2">
            <X />
            Close
          </span>
        </Button>
      </Row>
    </AlertDialog>
  );
}
