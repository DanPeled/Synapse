"use client";

import { useEffect, useMemo, useState } from "react";
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
import {
  CameraPerformanceProto,
  CameraProto,
  SetCameraRecordingStatusMessageProto,
} from "@/generated/messages/v1/camera";
import {
  PipelineProto,
  PipelineTypeProto,
  SetPipelineIndexMessageProto,
  SetPipelineTypeMessageProto,
  SetPipleineSettingMessageProto,
} from "@/generated/messages/v1/pipeline";
import {
  MessageProto,
  MessageTypeProto,
} from "@/generated/messages/v1/message";
import { SaveActionsDialog } from "./save_actions";
import {
  PipelineID,
  PipelineResultMap,
} from "@/services/backend/dataStractures";

interface CameraViewProps {
  selectedCamera?: CameraProto;
  cameraPerformance?: CameraPerformanceProto;
}

function CameraView({ selectedCamera, cameraPerformance }: CameraViewProps) {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="flex flex-col h-[400px] border-gray-700"
    >
      <CardHeader className="shrink-0">
        <Row className="items-center justify-between">
          <CardTitle
            className="flex items-center gap-2"
            style={{ color: teamColor }}
          >
            <Camera className="w-5 h-5" />
            Camera Stream
          </CardTitle>

          <Badge
            variant="secondary"
            className="bg-stone-700"
            style={{ color: teamColor }}
          >
            <Activity className="w-3 h-3 mr-1" />
            Processing @ {cameraPerformance?.fps ?? 0} FPS –{" "}
            {cameraPerformance
              ? cameraPerformance.latencyProcess.toFixed(2)
              : "0.00"}
            ms latency
          </Badge>
        </Row>
      </CardHeader>

      <CardContent className="flex-1 min-h-0 p-0">
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
    pipelineresults,
    cameraperformance,
    recordingstatuses,
  } = useBackendContext();

  // ===== State: only indexes / minimal info =====
  const [selectedCameraIndex, setSelectedCameraIndex] = useState(0);
  const [selectedPipelineIndex, setSelectedPipelineIndex] = useState(0);
  const [locked, setLocked] = useState(false);
  const [selectedCameraRecordingStatus, setSelectedCameraRecordingStatus] =
    useState(false);

  // ===== Derived objects =====
  const selectedCamera = useMemo(() => {
    if (!cameras) return undefined;
    const camData = cameras.get(selectedCameraIndex);
    return camData ? CameraProto.create(camData) : undefined;
  }, [cameras, selectedCameraIndex]);

  const selectedPipeline = pipelines
    ?.get(selectedCameraIndex)
    ?.get(selectedPipelineIndex);

  const selectedPipelineType = selectedPipeline
    ? pipelinetypes.get(selectedPipeline.type)
    : undefined;

  const selectedCameraPerformance = cameraperformance?.get(selectedCameraIndex);

  const selectedPipelineResults =
    selectedPipeline && pipelineresults?.get(selectedCameraIndex)
      ? pipelineresults.get(selectedCameraIndex)?.get(selectedPipeline.index)
      : undefined;

  useEffect(() => {
    setSelectedPipelineIndex(selectedCamera?.pipelineIndex ?? 0);
  }, [selectedCamera?.pipelineIndex]);

  // ===== Sync recording status =====
  useEffect(() => {
    if (selectedCamera) {
      const status = recordingstatuses.get(selectedCamera.index) ?? false;
      if (status !== selectedCameraRecordingStatus) {
        setSelectedCameraRecordingStatus(status);
      }
    }
  }, [selectedCamera, recordingstatuses]);

  // ===== Set document title once =====
  useEffect(() => {
    document.title = "Synapse Client";
  }, []);

  // ===== Update pipelines immutably =====
  function setPipelinesOfSelectedCamera(
    newpipelines: Map<PipelineID, PipelineProto>,
  ) {
    setPipelines((prev) => {
      const copy = new Map(prev);
      copy.set(selectedCameraIndex, newpipelines);
      return copy;
    });
  }

  function setPipelineIndexForSelectedCamera(newIndex: number) {
    const cameraPipelines = pipelines.get(selectedCameraIndex);
    if (!cameraPipelines || !cameraPipelines.has(newIndex)) return;

    setSelectedPipelineIndex(newIndex);

    // Send proto to server
    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX,
      setPipelineIndex: SetPipelineIndexMessageProto.create({
        cameraIndex: selectedCameraIndex ?? 0,
        pipelineIndex: newIndex,
      }),
    });
    socket?.sendBinary(MessageProto.encode(payload).finish());
  }
  // === Immutable update of pipelines for the selected camera ===
  function setPipelineTypeForSelectedCamera(newType?: PipelineTypeProto) {
    if (newType === undefined) return;
    if (selectedPipelineIndex === undefined) return;

    const cameraPipelines = pipelines.get(selectedCameraIndex) ?? new Map();
    const pipeline = cameraPipelines.get(selectedPipelineIndex);
    if (!pipeline) return;

    // Update pipeline locally
    const updatedPipeline: PipelineProto = { ...pipeline, type: newType.type };
    const updatedPipelines = new Map(cameraPipelines);
    updatedPipelines.set(selectedPipelineIndex, updatedPipeline);

    // Update top-level pipelines map immutably
    setPipelines((prev) => {
      const copy = new Map(prev);
      copy.set(selectedCameraIndex, updatedPipelines);
      return copy;
    });

    // Send type update to server
    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_TYPE_FOR_PIPELINE,
      setPipelineType: SetPipelineTypeMessageProto.create({
        newType: newType.type,
        cameraid: selectedCameraIndex,
        pipelineIndex: selectedPipelineIndex,
      }),
    });
    socket?.sendBinary(MessageProto.encode(payload).finish());
  }

  return (
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
        {" "}
        <Row gap="gap-2" className="h-full">
          {/* Camera + Pipeline Config */}{" "}
          <Column className="flex-[2] space-y-2 h-full">
            {" "}
            <CameraView
              selectedCamera={selectedCamera}
              cameraPerformance={selectedCameraPerformance}
            />
            <PipelineConfigControl
              pipelines={pipelines.get(selectedCameraIndex) ?? new Map()}
              cameraInfo={selectedCamera}
              setPipelines={setPipelinesOfSelectedCamera}
              selectedPipeline={selectedPipeline}
              selectedPipelineType={selectedPipelineType}
              backendConnected={connection.backend}
              setSetting={(val, setting, pipeline) => {
                if (hasSettingValue(val)) {
                  const payload = MessageProto.create({
                    type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_SETTING,
                    setPipelineSetting: SetPipleineSettingMessageProto.create({
                      pipelineIndex: pipeline.index,
                      cameraid: selectedCameraIndex,
                      value: val,
                      setting: setting,
                    }),
                  });

                  socket?.sendBinary(MessageProto.encode(payload).finish());
                }
              }}
              locked={locked}
            />
          </Column>
          {/* Controls + Results */}
          <Column className="flex-[1.2] space-y-2 h-full">
            <CameraAndPipelineControls
              cameras={cameras}
              pipelines={pipelines.get(selectedCameraIndex) ?? new Map()}
              pipelinetypes={pipelinetypes}
              socket={socket}
              selectedCameraIndex={selectedCameraIndex}
              setSelectedCameraIndexAction={setSelectedCameraIndex}
              selectedPipelineIndex={selectedPipelineIndex}
              setSelectedPipelineIndexAction={setPipelineIndexForSelectedCamera}
              selectedPipelineType={selectedPipelineType}
              setSelectedPipelineTypeAction={setPipelineTypeForSelectedCamera}
              setpipelinesAction={setPipelinesOfSelectedCamera}
            />

            <SaveActionsDialog
              locked={locked}
              setLocked={setLocked}
              save={() => {
                socket?.sendBinary(
                  MessageProto.encode(
                    MessageProto.create({
                      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SAVE,
                    }),
                  ).finish(),
                );
              }}
              recordingStatus={selectedCameraRecordingStatus}
              setRecordingStatus={(status) => {
                if (selectedCamera) {
                  const payload = MessageProto.create({
                    type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_CAMERA_RECORDING_STATUS,
                    setCameraRecordingStatus:
                      SetCameraRecordingStatusMessageProto.create({
                        cameraIndex: selectedCamera.index,
                        record: status,
                      }),
                  });
                  socket?.sendBinary(MessageProto.encode(payload).finish());
                }
              }}
            />

            <ResultsView results={selectedPipelineResults} />
          </Column>
        </Row>
      </div>
    </div>
  );
}
