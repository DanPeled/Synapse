import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Edit, Plus, Trash2, MoreVertical } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  teamColor,
  baseCardColor,
  hoverBg,
  borderColor,
} from "@/services/style";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import { Row } from "@/widgets/containers";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import ToggleButton from "@/widgets/toggleButtons";
import { Card, CardContent } from "@/components/ui/card";
import { CameraProto } from "@/proto/v1/camera";
import { WebSocketWrapper } from "@/services/websocket";
import { AddPipelineDialog } from "./addPipelineDialog";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { ChangePipelineTypeDialog } from "./change_pipeline_type_dialog";
import { ConfirmDeletePipelineDialog } from "./confirm_delete_pipeline_dialog";

interface CameraAndPipelineControlsProps {
  setSelectedPipeline: (val?: PipelineProto) => void;
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  setSelectedPipelineType: (val?: PipelineTypeProto) => void;
  selectedCamera: CameraProto | undefined;
  setSelectedCamera: (cam?: CameraProto) => void;
  cameras: CameraProto[];
  socket?: WebSocketWrapper;
  pipelines: Map<number, PipelineProto>;
  pipelinetypes: Map<string, PipelineTypeProto>;
}

export function CameraAndPipelineControls({
  setSelectedPipeline,
  selectedPipeline,
  selectedPipelineType,
  setSelectedPipelineType,
  selectedCamera,
  setSelectedCamera,
  cameras,
  socket,
  pipelines,
  pipelinetypes,
}: CameraAndPipelineControlsProps) {
  const [ignoreNetworkTablePipeline, setIgnoreNetworkTablePipeline] =
    useState(false);
  const [addPipelineDialogVisible, setAddPipelineDialogVisible] =
    useState(false);
  const [changePipelineTypeDialogVisible, setChangePipelineTypeDialogVisible] =
    useState(false);
  const [deletePipelineDialogVisible, setDeletePipelineDialogVisible] =
    useState<boolean>(false);
  const [requestedPipelineType, setRequestedPipelineType] = useState<
    PipelineTypeProto | undefined
  >(undefined);

  return (
    <Card
      style={{ backgroundColor: baseCardColor, color: teamColor }}
      className="border-gray-700"
    >
      <CardContent className="space-y-0">
        {/* Camera Selection */}
        <div className="space-y-0">
          <Dropdown
            value={selectedCamera}
            onValueChange={(val) => {
              setSelectedCamera(val);
            }}
            label="Camera"
            options={
              (cameras
                ? cameras.map((cam) => ({
                    label: `${cam?.name}`,
                    value: cam,
                  }))
                : []) as DropdownOption<CameraProto>[]
            }
          />
        </div>

        {/* Pipeline Selection */}
        <Row gap="gap-2" className="items-center">
          <Dropdown
            label="Pipeline"
            value={selectedPipeline}
            disabled={!ignoreNetworkTablePipeline}
            onValueChange={(val) => setSelectedPipeline(val)}
            options={Array.from(pipelines.entries()).map(
              ([index, pipeline]) => ({
                label: `${pipeline?.name} (#${index})`,
                value: pipeline,
              }),
            )}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                style={{
                  borderColor: borderColor,
                  color: teamColor,
                }}
              >
                <MoreVertical
                  className="w-4 h-4"
                  style={{ color: teamColor }}
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              side="bottom"
              align="end" // aligns to the start (left side of the trigger)
              alignOffset={20} // nudges it 20px to the left
              className="rounded-md shadow-lg bg-zinc-700"
              sideOffset={4}
              style={{
                borderColor: borderColor,
                borderWidth: "1px",
              }}
            >
              {[
                {
                  icon: (
                    <Edit className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Rename",
                  action: () => console.log("Rename clicked"),
                  disabled: () => selectedPipeline === undefined,
                },
                {
                  icon: (
                    <Plus className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Add Pipeline",
                  action: () => setAddPipelineDialogVisible(true),
                  disabled: () => false,
                },
                {
                  icon: (
                    <Copy className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Duplicate",
                  disabled: () => selectedPipeline === undefined,
                  action: () => {
                    if (selectedPipeline && selectedPipelineType) {
                      const payload = MessageProto.create({
                        type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
                        pipelineInfo: PipelineProto.create({
                          name: `Copy Of ${selectedPipeline.name}`,
                          type: selectedPipelineType.type,
                          index: Math.max(...Array.from(pipelines.keys())) + 1,
                          settingsValues: selectedPipeline.settingsValues ?? {},
                        }),
                      });

                      const binary = MessageProto.encode(payload).finish();
                      socket?.sendBinary(binary);
                    }
                  },
                },
                {
                  icon: (
                    <Trash2 className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Delete",
                  action: () => setDeletePipelineDialogVisible(true),
                  disabled: () => selectedPipeline === undefined,
                },
              ].map(({ icon, label, action, disabled }) => (
                <DropdownMenuItem
                  key={label}
                  disabled={disabled()}
                  className="flex items-center gap-2 text-sm font-medium px-3 py-2 rounded-md cursor-pointer"
                  style={{
                    color: teamColor,
                    transition: "background 0.15s ease",
                  }}
                  onClick={action}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor = hoverBg)
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                >
                  {icon}
                  {label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </Row>

        {/* Pipeline Type */}
        <Dropdown
          label="Pipeline Type"
          value={selectedPipelineType}
          onValueChange={(val) => {
            setRequestedPipelineType(val);
            setChangePipelineTypeDialogVisible(true);
          }}
          options={Array.from(pipelinetypes.entries()).map(([_, type]) => ({
            label: type.type,
            value: type,
          }))}
        />
        <div className="h-6" />
        <div className="flex justify-center items-center">
          <ToggleButton
            label="Ignore NetworkTables Pipeline"
            value={ignoreNetworkTablePipeline}
            onToggleAction={setIgnoreNetworkTablePipeline}
            tooltip="Toggle to ignore using the pipeline ID from the NetworkTable entry"
          />
        </div>
        {addPipelineDialogVisible && (
          <AddPipelineDialog
            visible={addPipelineDialogVisible}
            pipelineTypes={pipelinetypes}
            setVisible={setAddPipelineDialogVisible}
            socket={socket}
            index={Math.max(...Array.from(pipelines.keys())) + 1}
          />
        )}
        <ChangePipelineTypeDialog
          visible={changePipelineTypeDialogVisible}
          setVisible={setChangePipelineTypeDialogVisible}
          requestedType={requestedPipelineType}
          currentType={selectedPipelineType}
          setPipelineType={(val) => {
            setSelectedPipelineType(val);
            if (selectedPipeline && selectedPipelineType) {
              const payload = MessageProto.create({
                type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
                pipelineInfo: PipelineProto.create({
                  name: selectedPipeline.name,
                  type: val?.type ?? selectedPipeline.type,
                  index: selectedPipeline.index,
                  settingsValues: selectedPipeline.settingsValues ?? {},
                }),
              });

              const binary = MessageProto.encode(payload).finish();
              socket?.sendBinary(binary);
            }
          }}
        />
        {deletePipelineDialogVisible && (
          <ConfirmDeletePipelineDialog
            visible={deletePipelineDialogVisible}
            setVisible={setDeletePipelineDialogVisible}
            socket={socket}
          />
        )}
      </CardContent>
    </Card>
  );
}
