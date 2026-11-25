import { Card, CardHeader } from "@/components/ui/card";
import { SettingValueProto } from "@/generated/settings/v1/value";
import { CameraProto } from "@/generated/messages/v1/camera";
import {
  PipelineProto,
  PipelineTypeProto,
} from "@/generated/messages/v1/pipeline";
import {
  CameraPipelinesMap,
  CameraPipelinesSetter,
} from "@/services/backend/dataStractures";
import { generateControlFromSettingMeta } from "@/services/controls_generator";
import { baseCardColor, teamColor } from "@/services/style";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { JSX, useEffect, useState } from "react";
import * as Icons from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Row } from "@/widgets/containers";

function CategoryName({ text }: { text: string }) {
  const parts = text.split(/(<\w+\s*\/>)/g);

  return (
    <span className="inline-flex items-center gap-2 text-[1.1rem]">
      {parts.map((part, index) => {
        const match = part.match(/^<(\w+)\s*\/>$/);

        if (match) {
          const Icon = Icons[match[1] as keyof typeof Icons] as LucideIcon;

          return Icon ? (
            <Icon key={index} className="w-5 h-5 relative -top-[1px]" />
          ) : null;
        }

        return <span key={index}>{part}</span>;
      })}
    </span>
  );
}

export function PipelineConfigControl({
  selectedPipeline,
  selectedPipelineType,
  cameraInfo,
  backendConnected,
  setSetting,
  setPipelines,
  pipelines,
  locked,
}: {
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  cameraInfo?: CameraProto;
  backendConnected: boolean | undefined;
  setSetting: (
    val: SettingValueProto,
    setting: string,
    pipeline: PipelineProto,
  ) => void;
  setPipelines: CameraPipelinesSetter;
  pipelines: CameraPipelinesMap;
  locked: boolean;
}) {
  const [controls, setControls] = useState<
    Map<string, (JSX.Element | undefined)[]>
  >(new Map());

  function generateControls() {
    if (!selectedPipelineType || !backendConnected) {
      setControls(
        new Map([
          ["<Camera/> Camera Properties", []],
          ["Pipeline Config", []],
        ]),
      );
      return;
    }

    const newControls = new Map<string, (JSX.Element | undefined)[]>();

    selectedPipelineType.settings.forEach((setting) => {
      const control = generateControlFromSettingMeta({
        setting,
        selectedPipeline,
        setPipelines,
        setSetting,
        locked,
        pipelines,
      });

      if (!newControls.has(setting.category)) {
        newControls.set(setting.category, []);
      }

      newControls.get(setting.category)!.push(control);
    });

    cameraInfo?.settings.forEach((setting) => {
      const control = generateControlFromSettingMeta({
        setting: setting,
        selectedPipeline: selectedPipeline,
        setPipelines: setPipelines,
        setSetting: setSetting,
        locked: locked,
        pipelines: pipelines,
      });
      if (!newControls.has(setting.category)) {
        newControls.set(setting.category, []);
      }
      newControls.get(setting.category)!.push(control);
    });

    setControls(newControls);
  }

  useEffect(() => {
    generateControls();
  }, [
    selectedPipelineType,
    selectedPipeline,
    backendConnected,
    locked,
    cameraInfo,
  ]);

  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex-grow overflow-auto"
    >
      <CardHeader>
        <Row></Row>
        <Tabs
          defaultValue="<Camera/> Camera Properties"
          className="w-full"
          style={{ color: teamColor }}
        >
          <TabsList
            className="grid w-full border-gray-600 rounded-xl gap-2 text-sm"
            style={{
              backgroundColor: baseCardColor,
              gridTemplateColumns: `repeat(${controls.size}, minmax(0, 1fr))`,
            }}
          >
            {Array.from(controls.entries())
              .sort(([a], [b]) => {
                if (a.includes("Camera Properties")) return -1;
                if (b.includes("Camera Properties")) return 1;
                return 0;
              })
              .map(([category]) => (
                <TabsTrigger
                  key={category}
                  value={category}
                  className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer h-9"
                >
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    <CategoryName text={category} />{" "}
                  </div>
                </TabsTrigger>
              ))}
          </TabsList>

          {Array.from(controls.entries()).map(([category, items]) => (
            <TabsContent
              key={category}
              value={category}
              className="p-3 space-y-0 pt-1 text-sm"
            >
              <div style={{ color: teamColor }}>
                {items.length > 0 ? (
                  <div>{items}</div>
                ) : (
                  <div className="text-center" style={{ color: teamColor }}>
                    <CategoryName text={category} />
                    <p className="text-sm select-none">
                      Configure {category.toLowerCase()} parameters
                    </p>
                  </div>
                )}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </CardHeader>
    </Card>
  );
}
