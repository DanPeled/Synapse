"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  background,
  teamColor,
  baseCardColor,
} from "@/services/style";
import { CameraStream } from "@/widgets/cameraStream";
import { Column, Row } from "@/widgets/containers";
import { useBackendContext } from "@/services/backend/backendContext";
import { ResultsView } from "./results_view";
import { CameraAndPipelineControls } from "./camera_and_pipeline_control";
import { PipelineConfigControl } from "./pipeline_config_control";
import { Activity, Camera } from "lucide-react";

function CameraView() {
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
            <Badge variant="secondary" className="bg-red-600">
              <Activity className="w-3 h-3 mr-1" />
              Processing @ 0 FPS – 0ms latency
            </Badge>
          </Row>
        </Row>
      </CardHeader>

      <CardContent className="flex-grow flex flex-col items-center justify-center">
        <CameraStream />
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const { pipelinecontext, setPipelinecontext, connection } =
    useBackendContext();
  const [selectedPipeline, setSelectedPipeline] = useState(
    pipelinecontext.pipelines.get(0),
  );
  const [selectedPipelineType, setSelectedPipelineType] = useState(
    Array.from(pipelinecontext.pipelineTypes.values()).at(0),
  );

  useEffect(() => {
    if (connection.backend) {
      setSelectedPipeline(pipelinecontext.pipelines.get(0));
      setSelectedPipelineType(
        Array.from(pipelinecontext.pipelineTypes.values()).at(0),
      );
    }
  }, [pipelinecontext]);

  useEffect(() => {
    if (selectedPipeline) {
      const updated = pipelinecontext.pipelines.get(selectedPipeline.index);
      if (updated) {
        setSelectedPipeline(updated);
        setSelectedPipelineType(pipelinecontext.pipelineTypes.get(updated.type));
      }
    }
  }, [pipelinecontext]);

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
        <Row gap="gap-2" className="h-full">
          <Column className="flex-[2] space-y-2 h-full">
            <CameraView />
            <PipelineConfigControl
              pipelinecontext={pipelinecontext}
              selectedPipeline={selectedPipeline}
              selectedPipelineType={selectedPipelineType}
              setpipelinecontext={setPipelinecontext}
              backendConnected={connection.backend}
            />
          </Column>

          <Column className="flex-[1.2] space-y-2 h-full">
            <CameraAndPipelineControls
              pipelinecontext={pipelinecontext}
              setSelectedPipeline={(val) => {
                if (val !== undefined) {
                  setSelectedPipeline(val);
                  setSelectedPipelineType(pipelinecontext.pipelineTypes.get(val.type));
                }
              }}
              selectedPipeline={selectedPipeline}
              setSelectedPipelineType={setSelectedPipelineType}
              selectedPipelineType={selectedPipelineType}
            />
            <ResultsView />
          </Column>
        </Row>
      </div>
    </div>
  );
}
