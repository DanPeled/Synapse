"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { background, teamColor, baseCardColor } from "@/services/style";
import { CameraStream } from "@/widgets/cameraStream";
import { Column, Row } from "@/widgets/containers";
import {
  hasSettingValue,
  useBackendContext,
} from "@/services/backend/backendContext";
import { ResultsView } from "./results_view";
import { CameraAndPipelineControls } from "./camera_and_pipeline_control";
import { PipelineConfigControl } from "./pipeline_config_control";
import { Activity, Camera } from "lucide-react";
import { CameraStepControl } from "./camera_step_control";
import { CameraProto } from "@/proto/v1/camera";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import {
  SetPipelineIndexMessageProto,
  SetPipelineTypeMessageProto,
  SetPipleineSettingMessageProto,
} from "@/proto/v1/pipeline";
import { SaveActionsDialog } from "./save_actions";

interface CameraViewProps {
  selectedCamera?: CameraProto;
}

function CameraView({ selectedCamera }: CameraViewProps) {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex flex-col h-full max-h-[400px]"
    >
      <CardHeader>
        <Row className="items-center justify-between">
          <CardTitle
            className="flex items-center gap-2"
            style={{ color: teamColor }}
          >
            <Camera className="w-5 h-5" />
            Camera Stream
          </CardTitle>
          <Row gap="gap-2" className="items-center">
            <Badge
              variant="secondary"
              className="bg-stone-700"
              style={{ color: teamColor }}
            >
              <Activity className="w-3 h-3 mr-1" />
              Processing @ 0 FPS – 0ms latency
            </Badge>
          </Row>
        </Row>
      </CardHeader>

      <CardContent className="flex-grow flex flex-col items-center justify-center">
        <CameraStream stream={selectedCamera?.streamPath} />
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const {
    pipelines,
    connection,
    cameras,
    socket,
    setPipelines,
    pipelinetypes,
  } = useBackendContext();
  const [selectedPipeline, setSelectedPipeline] = useState(pipelines.get(0));
  const [selectedPipelineType, setSelectedPipelineType] = useState(
    Array.from(pipelinetypes.values()).at(0)!,
  );
  const [selectedCamera, setSelectedCamera] = useState(cameras.at(0));
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    let pipelineIndex =
      selectedCamera?.pipelineIndex ?? selectedPipeline?.index ?? 0;
    let pipeline = pipelines.get(pipelineIndex);

    if (!pipeline) {
      pipelineIndex = selectedCamera?.defaultPipeline ?? 0;
      pipeline = pipelines.get(pipelineIndex);
    }

    if (pipeline) {
      setSelectedPipeline(pipeline);

      const type = pipelinetypes.get(pipeline.type);
      if (type) {
        setSelectedPipelineType(type);
      } else {
        console.warn("Pipeline type not found for", pipeline.type);
      }
    } else {
      console.warn("No valid pipeline found for camera", selectedCamera);
    }
  }, [pipelines, pipelinetypes, selectedCamera]);

  useEffect(() => {
    if (cameras.length > 0) {
      setSelectedCamera(CameraProto.create(cameras.at(0)));
    }
  }, [cameras]);

  useEffect(() => {
    document.title = "Synapse Client";
  }, []);

  return (
    <>
      <div
        className="w-full min-h-screen text-pink-600"
        style={{ backgroundColor: background, color: teamColor }}
      >
        <div
          className="max-w-8xl mx-auto"
          style={{
            backgroundColor: background,
            borderRadius: "12px",
            padding: "10px",
          }}
        >
          <Row gap="gap-2" className="h-full">
            <Column className="flex-[2] space-y-2 h-full">
              <CameraView selectedCamera={selectedCamera} />
              <PipelineConfigControl
                pipelines={pipelines}
                setPipelines={setPipelines}
                selectedPipeline={selectedPipeline}
                selectedPipelineType={selectedPipelineType}
                backendConnected={connection.backend}
                setSetting={(val, setting, pipeline) => {
                  if (hasSettingValue(val)) {
                    const payload = MessageProto.create({
                      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_SETTING,
                      setPipelineSetting: SetPipleineSettingMessageProto.create(
                        {
                          pipelineIndex: pipeline.index,
                          value: val,
                          setting: setting,
                        },
                      ),
                    });

                    const binary = MessageProto.encode(payload).finish();
                    socket?.sendBinary(binary);
                  }
                }}
                locked={locked}
              />
            </Column>

            <Column className="flex-[1.2] space-y-2 h-full">
              <CameraAndPipelineControls
                setpipelines={setPipelines}
                pipelines={pipelines}
                pipelinetypes={pipelinetypes}
                socket={socket}
                setSelectedPipeline={(val) => {
                  if (val !== undefined) {
                    setSelectedPipeline(val);
                    setSelectedPipelineType(pipelinetypes.get(val.type)!);

                    if (selectedCamera) {
                      setTimeout(() => {
                        const payload = MessageProto.create({
                          type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX,
                          setPipelineIndex: SetPipelineIndexMessageProto.create(
                            {
                              cameraIndex: selectedCamera.index,
                              pipelineIndex: val.index,
                            },
                          ),
                        });

                        const binary = MessageProto.encode(payload).finish();
                        socket?.sendBinary(binary);
                      }, 0);
                    }
                  }
                }}
                selectedPipeline={selectedPipeline}
                setSelectedPipelineType={(newType) => {
                  setSelectedPipelineType(newType!);

                  setTimeout(() => {
                    if (selectedPipeline && newType) {
                      const payload = MessageProto.create({
                        type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_TYPE_FOR_PIPELINE,
                        setPipelineType: SetPipelineTypeMessageProto.create({
                          newType: newType.type,
                          pipelineIndex: selectedPipeline.index,
                        }),
                      });

                      const binary = MessageProto.encode(payload).finish();
                      socket?.sendBinary(binary);

                      selectedPipeline.type = newType.type;
                      const newPipelines = new Map(pipelines);
                      newPipelines.set(
                        selectedPipeline.index,
                        selectedPipeline,
                      );
                      setPipelines(newPipelines);
                    }
                  }, 0);
                }}
                selectedPipelineType={selectedPipelineType}
                cameras={cameras}
                setSelectedCamera={setSelectedCamera}
                selectedCamera={selectedCamera}
              />
              <SaveActionsDialog
                locked={locked}
                setLocked={setLocked}
                save={() => {
                  const payload = MessageProto.create({
                    type: MessageTypeProto.MESSAGE_TYPE_PROTO_SAVE,
                    removePipelineIndex: -1, // Forces me to put some payload
                  });

                  const binary = MessageProto.encode(payload).finish();
                  socket?.sendBinary(binary);
                }}
              />
              <ResultsView />
            </Column>
          </Row>
        </div>
      </div>
    </>
  );
}
