import { Button } from "@/components/ui/button";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { PipelineProto, RemovePipelineMessageProto } from "@/proto/v1/pipeline";
import { CameraID } from "@/services/backend/dataStractures";
import { teamColor } from "@/services/style";
import { WebSocketWrapper } from "@/services/websocket";
import { AlertDialog } from "@/widgets/alertDialog";
import { Column } from "@/widgets/containers";
import { Trash, TriangleAlert, X } from "lucide-react";

interface ConfirmDeletePipelineDialogProps {
  visible: boolean;
  setVisible: (val: boolean) => void;
  socket?: WebSocketWrapper;
  pipelineToBeDeleted?: PipelineProto;
  selectedCameraIndex?: CameraID;
  onRemovePipeline: (pipeline: PipelineProto) => void;
}

export function ConfirmDeletePipelineDialog({
  visible,
  setVisible,
  socket,
  pipelineToBeDeleted,
  selectedCameraIndex,
  onRemovePipeline,
}: ConfirmDeletePipelineDialogProps) {
  return (
    <AlertDialog
      visible={visible}
      onClose={() => setVisible(false)}
      className="w-[40vw] h-[30vh] -translate-y-40"
    >
      <Column>
        <h2 className="text-2xl flex items-center gap-2 text-center">
          <TriangleAlert className="text-yellow-400" />
          <span className="text-yellow-400 text-2xl">Warning:</span>
        </h2>
        <span style={{ color: teamColor }} className="text-2xl text-center">
          This action will delete the {pipelineToBeDeleted?.name} Pipeline and
          will not be able to be restored
        </span>
        <div className="h-5" />
        <Column gap="gap-2" style={{ color: teamColor }}>
          <Button
            variant="outline"
            className="rounded-md bg-zinc-800 hover:bg-zinc-700 text-lg cursor-pointer"
            style={{ color: teamColor }}
            onClick={() => {
              if (pipelineToBeDeleted) {
                const payload = MessageProto.create({
                  type: MessageTypeProto.MESSAGE_TYPE_PROTO_DELETE_PIPELINE,
                  removePipeline: RemovePipelineMessageProto.create({
                    removePipelineIndex: pipelineToBeDeleted?.index,
                    cameraid: selectedCameraIndex,
                  }),
                });

                const binary = MessageProto.encode(payload).finish();
                socket?.sendBinary(binary);
                onRemovePipeline(pipelineToBeDeleted);
              }
              setVisible(false);
            }}
          >
            <span className="flex items-center gap-2">
              <Trash />
              Delete Pipeline
            </span>
          </Button>

          <Button
            variant="outline"
            className="rounded-md bg-zinc-800 hover:bg-zinc-700 text-lg cursor-pointer"
            style={{ color: teamColor }}
            onClick={() => setVisible(false)}
          >
            <span className="flex items-center gap-2">
              <X />
              Cancel
            </span>
          </Button>
        </Column>
      </Column>
    </AlertDialog>
  );
}
