"use client";

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
import { Dropdown } from "@/widgets/dropdown";
import { Row } from "@/widgets/containers";
import { Card, CardContent } from "@/components/ui/card";
import TextInput from "@/widgets/textInput";
import {
  PipelineProto,
  PipelineTypeProto,
  SetPipelineNameMessageProto,
} from "@/proto/v1/pipeline";
import { CameraProto, SetDefaultPipelineMessageProto } from "@/proto/v1/camera";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { AddPipelineDialog } from "./addPipelineDialog";
import { ChangePipelineTypeDialog } from "./change_pipeline_type_dialog";
import { ConfirmDeletePipelineDialog } from "./confirm_delete_pipeline_dialog";
import {
  teamColor,
  baseCardColor,
  hoverBg,
  borderColor,
} from "@/services/style";
import { CameraID } from "@/services/backend/dataStractures";
import { WebSocketWrapper } from "@/services/websocket";

interface CameraAndPipelineControlsProps {
  selectedCameraIndex: number;
  setSelectedCameraIndexAction: (index: number) => void;
  selectedPipelineIndex: number;
  setSelectedPipelineIndexAction: (index: number) => void;
  selectedPipelineType?: PipelineTypeProto;
  setSelectedPipelineTypeAction: (val?: PipelineTypeProto) => void;
  cameras: Map<CameraID, CameraProto>;
  pipelines: Map<number, PipelineProto>;
  pipelinetypes: Map<string, PipelineTypeProto>;
  setpipelinesAction: (pipeline: Map<number, PipelineProto>) => void;
  socket?: WebSocketWrapper;
}

export function CameraAndPipelineControls({
  selectedCameraIndex,
  setSelectedCameraIndexAction: setSelectedCameraIndex,
  selectedPipelineIndex,
  setSelectedPipelineIndexAction: setSelectedPipelineIndex,
  selectedPipelineType,
  setSelectedPipelineTypeAction: setSelectedPipelineType,
  cameras,
  pipelines,
  pipelinetypes,
  setpipelinesAction: setpipelines,
  socket,
}: CameraAndPipelineControlsProps) {
  const [addPipelineDialogVisible, setAddPipelineDialogVisible] =
    useState(false);
  const [changePipelineTypeDialogVisible, setChangePipelineTypeDialogVisible] =
    useState(false);
  const [deletePipelineDialogVisible, setDeletePipelineDialogVisible] =
    useState(false);
  const [requestedPipelineType, setRequestedPipelineType] = useState<
    PipelineTypeProto | undefined
  >(undefined);
  const [renamingPipeline, setRenamingPipeline] = useState(false);
  const [newPipelineName, setNewPipelineName] = useState("New Pipeline");

  const selectedCamera = cameras.get(selectedCameraIndex);
  const selectedPipeline = pipelines.get(selectedPipelineIndex);

  useEffect(() => {
    if (renamingPipeline && selectedPipeline) {
      setNewPipelineName(selectedPipeline.name);
    }
  }, [renamingPipeline, selectedPipeline]);

  // Update pipeline name on server
  const renamePipeline = () => {
    if (!selectedPipeline || !selectedCamera) return;
    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_NAME,
      setPipelineName: SetPipelineNameMessageProto.create({
        pipelineIndex: selectedPipeline.index,
        cameraid: selectedCamera.index,
        name: newPipelineName,
      }),
    });
    socket?.sendBinary(MessageProto.encode(payload).finish());
    setRenamingPipeline(false);
  };

  // Set pipeline as default
  const setDefaultPipeline = () => {
    if (!selectedPipeline || !selectedCamera) return;
    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_DEFAULT_PIPELINE,
      setDefaultPipeline: SetDefaultPipelineMessageProto.create({
        cameraIndex: selectedCamera.index,
        pipelineIndex: selectedPipeline.index,
      }),
    });
    socket?.sendBinary(MessageProto.encode(payload).finish());
  };

  return (
    <>
      <Card
        style={{ backgroundColor: baseCardColor, color: teamColor }}
        className="border-gray-700"
      >
        {" "}
        <CardContent className="space-y-3">
          {/* Camera Selection */}
          <Dropdown
            label="Camera"
            value={selectedCameraIndex}
            onValueChange={(val) => setSelectedCameraIndex(val)}
            options={Array.from(cameras.values()).map((cam) => ({
              label: <span>{cam.name}</span>,
              value: cam.index,
              key: cam.index.toString(),
            }))}
          />
          {/* Pipeline Selection */}
          <Row gap="gap-2" className="items-center">
            {renamingPipeline ? (
              <>
                <TextInput
                  value={newPipelineName}
                  onChange={setNewPipelineName}
                  label="Pipeline Name"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setRenamingPipeline(false)}
                  className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                >
                  <Ban className="w-4 h-4" style={{ color: teamColor }} />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={renamePipeline}
                  className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                >
                  <Edit className="w-4 h-4" style={{ color: teamColor }} />
                </Button>
              </>
            ) : (
              <>
                <Dropdown
                  label="Pipeline"
                  value={selectedPipelineIndex}
                  onValueChange={(val) => setSelectedPipelineIndex(val)}
                  options={Array.from(pipelines.entries()).map(
                    ([index, pipeline]) => ({
                      label: (
                        <span className="inline-flex items-center gap-2">
                          {pipeline.name} (#{index}){" "}
                          {selectedCamera?.defaultPipeline ===
                            pipeline.index && (
                            <Star
                              className="w-4 h-4 text-yellow-500"
                              fill="yellow"
                            />
                          )}
                        </span>
                      ),
                      value: index,
                      key: index.toString(),
                    }),
                  )}
                />

                {/* Pipeline actions */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
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
                    style={{ borderColor: borderColor, borderWidth: "1px" }}
                  >
                    <DropdownMenuItem
                      onClick={() => setRenamingPipeline(true)}
                      disabled={!selectedPipeline}
                    >
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setAddPipelineDialogVisible(true)}
                    >
                      Add Pipeline
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={setDefaultPipeline}
                      disabled={!selectedPipeline}
                    >
                      Set As Default
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        if (!selectedPipeline || !selectedPipelineType) return;
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
                        socket?.sendBinary(
                          MessageProto.encode(payload).finish(),
                        );
                      }}
                      disabled={!selectedPipeline}
                    >
                      Duplicate
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setDeletePipelineDialogVisible(true)}
                      disabled={
                        !selectedPipeline ||
                        selectedPipeline.index ===
                          selectedCamera?.defaultPipeline
                      }
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </Row>

          {/* Pipeline Type */}
          <Dropdown
            label="Pipeline Type"
            value={selectedPipelineType?.type}
            onValueChange={(val) => {
              if (val === undefined) return;
              const type = pipelinetypes.get(val);
              setRequestedPipelineType(type);
              setChangePipelineTypeDialogVisible(true);
            }}
            options={Array.from(pipelinetypes.values())
              .filter(
                (type) =>
                  !(type.type.startsWith("$$") && type.type.endsWith("$$")),
              )
              .map((type) => ({
                label: type.type,
                value: type.type,
                key: type.type,
              }))}
          />
        </CardContent>
      </Card>

      {addPipelineDialogVisible && selectedCamera && (
        <AddPipelineDialog
          cameraid={selectedCamera.index}
          visible={addPipelineDialogVisible}
          pipelineTypes={pipelinetypes}
          setVisible={setAddPipelineDialogVisible}
          socket={socket}
          index={Math.max(...Array.from(pipelines.keys())) + 1}
        />
      )}

      {changePipelineTypeDialogVisible && (
        <ChangePipelineTypeDialog
          visible={changePipelineTypeDialogVisible}
          setVisible={setChangePipelineTypeDialogVisible}
          requestedType={requestedPipelineType}
          currentType={selectedPipelineType}
          setPipelineType={(val) => {
            setSelectedPipelineType(val);
            if (selectedPipeline) {
              const payload = MessageProto.create({
                type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
                pipelineInfo: PipelineProto.create({
                  name: selectedPipeline.name,
                  type: val?.type ?? selectedPipeline.type,
                  index: selectedPipeline.index,
                  settingsValues: selectedPipeline.settingsValues ?? {},
                }),
              });
              socket?.sendBinary(MessageProto.encode(payload).finish());
            }
          }}
        />
      )}

      {deletePipelineDialogVisible && selectedCamera && selectedPipeline && (
        <ConfirmDeletePipelineDialog
          visible={deletePipelineDialogVisible}
          setVisible={setDeletePipelineDialogVisible}
          selectedCameraIndex={selectedCamera.index}
          socket={socket}
          pipelineToBeDeleted={selectedPipeline}
          onRemovePipeline={(pipeline) => {
            const newPipelines = new Map(pipelines);
            newPipelines.delete(pipeline.index);
            setpipelines(newPipelines);
          }}
        />
      )}
    </>
  );
}
