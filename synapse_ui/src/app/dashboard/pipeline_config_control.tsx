import { Card, CardHeader } from "@/components/ui/card";
import { SettingValueProto } from "@/proto/settings/v1/value";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { hasSettingValue } from "@/services/backend/backendContext";
import {
  GenerateControl,
  settingValueToProto,
} from "@/services/controls_generator";
import { baseCardColor, teamColor } from "@/services/style";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { Activity, Camera, Settings } from "lucide-react";
import { JSX, useEffect, useState } from "react";

export function PipelineConfigControl({
  selectedPipeline,
  selectedPipelineType,
  backendConnected,
  setSetting,
  setPipelines,
  pipelines,
  locked,
}: {
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  backendConnected: boolean | undefined;
  setSetting: (
    val: SettingValueProto,
    setting: string,
    pipeline: PipelineProto,
  ) => void;
  setPipelines: (val: Map<number, PipelineProto>) => void;
  pipelines: Map<number, PipelineProto>;
  locked: boolean;
}) {
  const [cameraControls, setCameraControls] = useState<
    (JSX.Element | undefined)[]
  >([]);
  const [pipelineControls, setPipelineControls] = useState<
    (JSX.Element | undefined)[]
  >([]);

  function generateControls() {
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
            if (hasSettingValue(val)) {
              setTimeout(() => {
                if (selectedPipeline) {
                  const oldPipelines = pipelines;

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
                  setPipelines(newPipelines);
                }
              }, 0);

              setTimeout(() => {
                setSetting(val, setting.name, selectedPipeline!);
              }, 0);
            }
          }}
          value={
            selectedPipeline?.settingsValues[setting.name] ??
            setting.default ??
            settingValueToProto("")
          }
          defaultValue={setting.default}
          locked={locked}
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
  }

  useEffect(() => {
    generateControls();
  }, [selectedPipelineType, selectedPipeline, backendConnected, locked]);

  useEffect(() => {
    generateControls();
  }, [locked]);

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
            className="grid w-full grid-cols-2 border-gray-600 rounded-xl gap-2"
            style={{ backgroundColor: baseCardColor }}
          >
            <TabsTrigger
              value="input"
              className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer h-8"
            >
              Input
            </TabsTrigger>
            <TabsTrigger
              value="pipeline"
              className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer"
            >
              {selectedPipelineType?.type ?? "Pipeline"}
            </TabsTrigger>
            {/* <TabsTrigger */}
            {/*   value="output" */}
            {/*   className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer" */}
            {/* > */}
            {/*   Output */}
            {/* </TabsTrigger> */}
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

          {/* <TabsContent value="output" className="p-6"> */}
          {/*   <div className="text-center" style={{ color: teamColor }}> */}
          {/*     <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" /> */}
          {/*     <p className="select-none">Output Configuration</p> */}
          {/*     <p className="text-sm select-none"> */}
          {/*       Configure output streams and data */}
          {/*     </p> */}
          {/*   </div> */}
          {/* </TabsContent> */}
        </Tabs>
      </CardHeader>
    </Card>
  );
}
