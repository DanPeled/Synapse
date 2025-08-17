import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Copy,
  Edit,
  Plus,
  Trash2,
  MoreVertical,
  Star,
  Ban,
} from "lucide-react";
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
import { Dropdown } from "@/widgets/dropdown";
import { Row } from "@/widgets/containers";
import {
  PipelineProto,
  PipelineTypeProto,
  SetPipelineNameMessageProto,
} from "@/proto/v1/pipeline";
import { Card, CardContent } from "@/components/ui/card";
import { CameraProto, SetDefaultPipelineMessageProto } from "@/proto/v1/camera";
import { WebSocketWrapper } from "@/services/websocket";
import { AddPipelineDialog } from "./addPipelineDialog";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { ChangePipelineTypeDialog } from "./change_pipeline_type_dialog";
import { ConfirmDeletePipelineDialog } from "./confirm_delete_pipeline_dialog";
import TextInput from "@/widgets/textInput";
import { CameraID } from "@/services/backend/dataStractures";

interface CameraAndPipelineControlsProps {
  setSelectedPipeline: (val?: PipelineProto) => void;
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  setSelectedPipelineType: (val?: PipelineTypeProto) => void;
  selectedCamera: CameraProto | undefined;
  setSelectedCamera: (cam?: CameraProto) => void;
  cameras: Map<CameraID, CameraProto>;
  socket?: WebSocketWrapper;
  pipelines: Map<number, PipelineProto>;
  setpipelines: (pipeline: Map<number, PipelineProto>) => void;
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
  setpipelines,
  pipelinetypes,
}: CameraAndPipelineControlsProps) {
  const [addPipelineDialogVisible, setAddPipelineDialogVisible] =
    useState(false);
  const [changePipelineTypeDialogVisible, setChangePipelineTypeDialogVisible] =
    useState(false);
  const [deletePipelineDialogVisible, setDeletePipelineDialogVisible] =
    useState<boolean>(false);
  const [requestedPipelineType, setRequestedPipelineType] = useState<
    PipelineTypeProto | undefined
  >(undefined);

  const [renamingPipeline, setRenamingPipeline] = useState<boolean>(false);
  const [newPipelineName, setNewPipelineName] =
    useState<string>("New Pipeline");

  useEffect(() => {
    if (selectedPipeline && renamingPipeline) {
      setNewPipelineName(selectedPipeline.name);
    }
  }, [renamingPipeline]);

  return (
    <>
      <Card
        style={{ backgroundColor: baseCardColor, color: teamColor }}
        className="border-gray-700"
      >
        <CardContent className="space-y-3">
          {/* Camera Selection */}
          <div className="space-y-0">
            <Dropdown
              value={selectedCamera}
              onValueChange={(val) => {
                setSelectedCamera(val);
              }}
              label="Camera"
              options={Array.from(cameras?.values() ?? []).map((cam) => ({
                label: <span>{cam.name}</span>,
                value: cam,
                key: cam.name,
              }))}
            />
          </div>

          {/* Pipeline Selection */}
          <Row gap="gap-2" className="items-center">
            {renamingPipeline ? (
              <>
                <TextInput
                  value={newPipelineName}
                  onChange={(val) => setNewPipelineName(val)}
                  label="Pipeline Name"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                  style={{
                    borderColor: borderColor,
                    color: teamColor,
                  }}
                  onClick={() => {
                    setRenamingPipeline(false);
                  }}
                >
                  <Ban className="w-4 h-4" style={{ color: teamColor }} />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                  style={{
                    borderColor: borderColor,
                    color: teamColor,
                  }}
                  onClick={() => {
                    if (selectedPipeline) {
                      const payload = MessageProto.create({
                        type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_NAME,
                        setPipelineName: SetPipelineNameMessageProto.create({
                          name: newPipelineName,
                          pipelineIndex: selectedPipeline.index,
                        }),
                      });

                      const binary = MessageProto.encode(payload).finish();
                      socket?.sendBinary(binary);
                    }

                    setRenamingPipeline(false);
                  }}
                >
                  <Edit className="w-4 h-4" style={{ color: teamColor }} />
                </Button>
              </>
            ) : (
              <>
                <Dropdown
                  label="Pipeline"
                  value={selectedPipeline}
                  onValueChange={(val) => setSelectedPipeline(val)}
                  options={Array.from(pipelines.entries()).map(
                    ([index, pipeline]) => ({
                      label: (
                        <span className="inline-flex items-center gap-2">
                          {pipeline?.name} (#{index}){" "}
                          {selectedCamera?.defaultPipeline == pipeline.index ? (
                            <Star
                              className="w-4 h-4 text-yellow-500"
                              fill="yellow"
                            />
                          ) : undefined}
                        </span>
                      ),
                      value: pipeline,
                      key: pipeline.index.toString(),
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
                    align="end"
                    alignOffset={20}
                    className="rounded-md shadow-lg bg-zinc-800"
                    style={{
                      borderColor: borderColor,
                      borderWidth: "1px",
                    }}
                  >
                    {[
                      {
                        icon: (
                          <Edit
                            className="w-4 h-4"
                            style={{ color: teamColor }}
                          />
                        ),
                        label: "Rename",
                        action: () => setRenamingPipeline(true),
                        disabled: () => selectedPipeline === undefined,
                      },
                      {
                        icon: (
                          <Plus
                            className="w-4 h-4"
                            style={{ color: teamColor }}
                          />
                        ),
                        label: "Add Pipeline",
                        action: () => setAddPipelineDialogVisible(true),
                        disabled: () => false,
                      },
                      {
                        icon: (
                          <Star
                            className="w-4 h-4"
                            style={{ color: teamColor }}
                          />
                        ),
                        label: "Set As Default",
                        action: () => {
                          if (selectedPipeline && selectedCamera) {
                            const payload = MessageProto.create({
                              type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_DEFAULT_PIPELINE,
                              setDefaultPipeline:
                                SetDefaultPipelineMessageProto.create({
                                  cameraIndex: selectedCamera.index,
                                  pipelineIndex: selectedPipeline.index,
                                }),
                            });

                            const binary =
                              MessageProto.encode(payload).finish();
                            socket?.sendBinary(binary);
                          }
                        },
                        disabled: () => selectedPipeline === undefined,
                      },
                      {
                        icon: (
                          <Copy
                            className="w-4 h-4"
                            style={{ color: teamColor }}
                          />
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
                                index:
                                  Math.max(...Array.from(pipelines.keys())) + 1,
                                settingsValues:
                                  selectedPipeline.settingsValues ?? {},
                              }),
                            });

                            const binary =
                              MessageProto.encode(payload).finish();
                            socket?.sendBinary(binary);
                          }
                        },
                      },
                      {
                        icon: (
                          <Trash2
                            className="w-4 h-4"
                            style={{ color: teamColor }}
                          />
                        ),
                        label: "Delete",
                        action: () => setDeletePipelineDialogVisible(true),
                        disabled: () =>
                          selectedPipeline === undefined ||
                          selectedPipeline.index ==
                            selectedCamera?.defaultPipeline,
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
                          (e.currentTarget.style.backgroundColor =
                            "transparent")
                        }
                      >
                        {icon}
                        {label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </Row>

          {/* Pipeline Type */}
          <Dropdown
            label="Pipeline Type"
            value={selectedPipelineType}
            onValueChange={(val) => {
              setRequestedPipelineType(val);
              setChangePipelineTypeDialogVisible(true);
            }}
            options={Array.from(pipelinetypes.values())
              .filter((type: PipelineTypeProto) => {
                return !(
                  type.type.startsWith("$$") && type.type.endsWith("$$")
                );
              })
              .map((type) => ({
                label: type.type,
                value: type,
                key: type.type,
              }))}
          />
        </CardContent>
      </Card>
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
          pipelineToBeDeleted={selectedPipeline}
          onRemovePipeline={(pipeline) => {
            const newPipelines = pipelines;
            newPipelines.delete(pipeline.index);
            setpipelines(newPipelines);
          }}
        />
      )}
    </>
  );
}
