import { Card, CardHeader } from "@/components/ui/card";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { PipelineManagement } from "@/services/backend/pipelineContext";
import { GenerateControl } from "@/services/controls_generator";
import { baseCardColor, teamColor } from "@/services/style";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { Activity, Camera, Settings } from "lucide-react";
import { JSX, useEffect, useState } from "react";

export function PipelineConfigControl({
  pipelinecontext,
  selectedPipeline,
  selectedPipelineType,
  setpipelinecontext,
  backendConnected,
}: {
  pipelinecontext: PipelineManagement.PipelineContext;
  setpipelinecontext: (context: PipelineManagement.PipelineContext) => void;
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  backendConnected: boolean | undefined;
}) {
  const [cameraControls, setCameraControls] = useState<
    (JSX.Element | undefined)[]
  >([]);
  const [pipelineControls, setPipelineControls] = useState<
    (JSX.Element | undefined)[]
  >([]);

  useEffect(() => {
    if (!selectedPipelineType || !backendConnected) {
      setCameraControls([]);
      setPipelineControls([]);
      return;
    }

    const cameraItems: (JSX.Element | undefined)[] = [];
    const pipelineItems: (JSX.Element | undefined)[] = [];

    selectedPipelineType.settings.forEach((setting) => {
      const control = (
        <GenerateControl
          key={setting.name + setting.category}
          setting={setting}
          setValue={(val) => {
            setTimeout(() => {
              if (selectedPipeline && pipelinecontext) {
                const oldPipelines = pipelinecontext.pipelines;

                const newSettingsValues = {
                  ...selectedPipeline.settingsValues,
                  [setting.name]: val,
                };

                const updatedPipeline = {
                  ...selectedPipeline,
                  settingsValues: newSettingsValues,
                };

                const newPipelines = new Map(oldPipelines);
                newPipelines.set(selectedPipeline.index, updatedPipeline);

                setpipelinecontext({
                  ...pipelinecontext,
                  pipelines: newPipelines,
                });
              }
            }, 0);
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
  }, [selectedPipelineType, selectedPipeline, backendConnected]);

  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex-grow overflow-auto"
    >
      <CardHeader>
        <Tabs
          defaultValue="input"
          className="w-full"
          style={{ color: teamColor }}
        >
          <TabsList
            className="grid w-full grid-cols-3 border-gray-600 rounded-xl"
            style={{ backgroundColor: baseCardColor }}
          >
            <TabsTrigger
              value="input"
              className="rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer"
            >
              Input
            </TabsTrigger>
            <TabsTrigger
              value="pipeline"
              className="rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer"
            >
              Pipeline
            </TabsTrigger>
            <TabsTrigger
              value="output"
              className="rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer"
            >
              Output
            </TabsTrigger>
          </TabsList>

          <TabsContent value="input" className="p-6 space-y-6">
            <div style={{ color: teamColor }}>
              {cameraControls.length > 0 ? (
                <div className="space-y-2">{cameraControls}</div>
              ) : (
                <div className="text-center" style={{ color: teamColor }}>
                  <Camera className="w-16 h-16 mx-auto mb-2 opacity-50" />
                  <p className="select-none">Camera Settings</p>
                  <p className="text-sm select-none">
                    Configure camera parameters
                  </p>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="pipeline" className="p-6 space-y-6">
            <div style={{ color: teamColor }}>
              {pipelineControls.length > 0 ? (
                <div className="space-y-2">{pipelineControls}</div>
              ) : (
                <div className="text-center" style={{ color: teamColor }}>
                  <Settings className="w-16 h-16 mx-auto mb-2 opacity-50" />
                  <p className="select-none">Pipeline Settings</p>
                  <p className="text-sm select-none">
                    Configure pipeline-specific parameters
                  </p>
                </div>
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
      </CardHeader>
    </Card>
  );
}
