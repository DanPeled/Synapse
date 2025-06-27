"use client";

import { JSX, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Camera,
  Settings,
  Copy,
  Edit,
  Plus,
  Trash2,
  MoreVertical,
  Activity,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  background,
  teamColor,
  baseCardColor,
  hoverBg,
  borderColor,
} from "@/services/style";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import { CameraStream } from "@/widgets/cameraStream";
import { Column, Row } from "@/widgets/containers";
import { useBackendContext } from "@/services/backend/backendContext";
import { PipelineManagement } from "@/services/backend/pipelineContext";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { GenerateControl } from "@/services/controls_generator";
import { toTitleCase } from "@/services/stringUtil";

const mockData = {
  cameras: [
    { label: "Monochrome (#0)", value: 0 },
    { label: "Colored (#1)", value: 1 },
  ],
  resolutions: [
    { label: "1920x1080 @ 100FPS", value: "1920x1080" },
    { label: "1280x720 @ 100FPS", value: "1280x720" },
    { label: "640x480 @ 100FPS", value: "640x480" },
  ],
  orientations: [
    { label: "Normal", value: 0 },
    { label: "90deg CW", value: 90 },
    { label: "180deg", value: 180 },
    { label: "90deg CCW", value: 270 },
  ],
};

function CameraAndPipelineControls({
  pipelinecontext,
  setSelectedPipeline,
  selectedPipeline,
  selectedPipelineType,
  setSelectedPipelineType
}: {
  pipelinecontext: PipelineManagement.PipelineContext,
  setSelectedPipeline: (val?: PipelineProto) => void,
  selectedPipeline?: PipelineProto,
  selectedPipelineType?: PipelineTypeProto,
  setSelectedPipelineType: (val?: PipelineTypeProto) => void
}) {
  const [selectedCamera, setSelectedCamera] = useState(
    mockData.cameras[0].value,
  );


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
            options={mockData.cameras as DropdownOption<number>[]}
          />
        </div>

        {/* Pipeline Selection */}
        <Row gap="gap-2" className="items-center">
          <Dropdown
            label="Pipeline"
            value={selectedPipeline}
            onValueChange={(val) => setSelectedPipeline(val)}
            options={Array.from(pipelinecontext.pipelines.entries()).map(
              ([index, pipeline]) => ({
                label: pipeline.name,
                value: pipeline,
              }),
            )}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="rounded-md"
                style={{
                  backgroundColor: baseCardColor,
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
              className="rounded-md shadow-lg"
              sideOffset={4}
              style={{
                backgroundColor: baseCardColor,
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
                },
                {
                  icon: (
                    <Plus className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Add Pipeline",
                },
                {
                  icon: (
                    <Copy className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Duplicate",
                },
                {
                  icon: (
                    <Trash2 className="w-4 h-4" style={{ color: teamColor }} />
                  ),
                  label: "Delete",
                },
              ].map(({ icon, label }) => (
                <DropdownMenuItem
                  key={label}
                  className="flex items-center gap-2 text-sm font-medium px-3 py-2 rounded-md"
                  style={{
                    color: teamColor,
                    transition: "background 0.15s ease",
                  }}
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
        <div className="space-y-2">
          <Dropdown
            label="Pipeline Type"
            value={selectedPipelineType}
            onValueChange={(val) => setSelectedPipelineType(val)}
            options={Array.from(pipelinecontext.pipelineTypes.entries()).map(
              ([_, type]) => ({
                label: type.type,
                value: type,
              }),
            )}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function CameraView() {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex flex-col h-full max-h-[400px]"
    >
      <CardHeader className="pb-2">
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

function PipelineConfigControl({
  selectedPipeline,
  selectedPipelineType,
}: {
  pipelinecontext: PipelineManagement.PipelineContext,
  selectedPipeline?: PipelineProto,
  selectedPipelineType?: PipelineTypeProto,
}) {
  const [cameraControls, setCameraControls] = useState<(JSX.Element | undefined)[]>([]);
  const [pipelineControls, setPipelineControls] = useState<(JSX.Element | undefined)[]>([]);

  useEffect(() => {
    if (!selectedPipelineType) {
      setCameraControls([]);
      setPipelineControls([]);
      return;
    }

    const cameraItems: (JSX.Element | undefined)[] = [];
    const pipelineItems: (JSX.Element | undefined)[] = [];

    selectedPipelineType.settings.forEach((setting) => {
      const control = (
        <GenerateControl
          key={toTitleCase(setting.name)}
          setting={setting}
          setValue={(val) => {
            if (selectedPipeline) {
              selectedPipeline.settingsValues[setting.name] = val;
            }
          }}
          value={selectedPipeline!.settingsValues[setting.name]}
          defaultValue={setting.default}
        />
      );

      if (setting.category === "Camera Properties") {
        cameraItems.push(control);
      } else {
        pipelineItems.push(control);
      }
    });

    setCameraControls(cameraItems);
    setPipelineControls(pipelineItems);
  }, [selectedPipelineType, selectedPipeline]);


  // TODO: retain state (doesnt affect pipeline context currently)

  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex-grow overflow-auto"
    >
      <CardContent className="p-0">
        <Tabs defaultValue="input" className="w-full">
          <TabsList
            className="grid w-full grid-cols-3 border-gray-600"
            style={{ backgroundColor: baseCardColor }}
          >
            <TabsTrigger
              value="input"
              className="data-[state=active]:bg-pink-800 cursor-pointer"
            >
              Input
            </TabsTrigger>
            <TabsTrigger
              value="pipeline"
              className="data-[state=active]:bg-pink-800 cursor-pointer"
            >
              Pipeline
            </TabsTrigger>
            <TabsTrigger
              value="output"
              className="data-[state=active]:bg-pink-800 cursor-pointer"
            >
              Output
            </TabsTrigger>
          </TabsList>

          <TabsContent value="input" className="p-6 space-y-6">
            <div>
              {...cameraControls}
            </div>
          </TabsContent>

          <TabsContent value="pipeline" className="p-6 space-y-6">
            <div style={{ color: teamColor }}>
              {pipelineControls.length > 0 ? (
                <div className="space-y-4">
                  {pipelineControls}
                </div>
              ) : (
                <>
                  <Settings className="w-16 h-16 mx-auto mb-2 opacity-50" />
                  <p className="select-none">Pipeline Settings</p>
                  <p className="text-sm select-none">
                    Configure pipeline-specific parameters
                  </p>
                </>
              )}
            </div>
          </TabsContent>

          <TabsContent value="output" className="p-6">
            <div className="text-center" style={{ color: teamColor }}>
              <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" />
              <p className="select-none">Output Configuration</p>
              <p className="text-sm select-none">
                Configure output streams and data
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function ResultsView() {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 h-full flex flex-col"
    >
      <CardHeader></CardHeader>
      <CardContent
        className="flex-grow flex items-center justify-center min-h-140"
        style={{ color: teamColor }}
      >
        <div className="text-center">
          <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" />
          <p className="select-none">Pipeline Results</p>
          <p className="text-sm select-none">Results will appear here</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const { pipelinecontext: pipelinecontext, connection } = useBackendContext();
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
  }, [connection.backend, pipelinecontext]);

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
        {/* Left Column */}
        <Row gap="gap-2" className="h-full">
          <Column className="flex-[2] space-y-2 h-full">
            <CameraView />
            <PipelineConfigControl
              pipelinecontext={pipelinecontext}
              selectedPipeline={selectedPipeline}
              selectedPipelineType={selectedPipelineType} />
          </Column>

          <Column className="flex-[1.2] space-y-2 h-full">
            <CameraAndPipelineControls pipelinecontext={pipelinecontext}
              setSelectedPipeline={setSelectedPipeline}
              selectedPipeline={selectedPipeline}
              setSelectedPipelineType={setSelectedPipelineType}
              selectedPipelineType={selectedPipelineType} />
            <ResultsView />
          </Column>
        </Row>
      </div>
    </div>
  );
}
