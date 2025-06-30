import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Copy,
  Edit,
  Plus,
  Trash2,
  MoreVertical,
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
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import { Row } from "@/widgets/containers";
import { PipelineManagement } from "@/services/backend/pipelineContext";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import ToggleButton from "@/widgets/toggleButtons";
import { Card, CardContent } from "@/components/ui/card";

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

export function CameraAndPipelineControls({
  pipelinecontext,
  setSelectedPipeline,
  selectedPipeline,
  selectedPipelineType,
  setSelectedPipelineType,
}: {
  pipelinecontext: PipelineManagement.PipelineContext;
  setSelectedPipeline: (val?: PipelineProto) => void;
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  setSelectedPipelineType: (val?: PipelineTypeProto) => void;
}) {
  const [selectedCamera, setSelectedCamera] = useState(
    mockData.cameras[0].value,
  );
  const [ignoreNetworkTablePipeline, setIgnoreNetworkTablePipeline] = useState(false);

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
            disabled={!ignoreNetworkTablePipeline}
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
        <div className="h-6" />
        <div className="flex justify-center items-center">
          <ToggleButton
            label="Ignore NetworkTables Pipeline"
            value={ignoreNetworkTablePipeline}
            onToggleAction={setIgnoreNetworkTablePipeline}
            tooltip="Toggle to ignore using the pipeline ID from the NetworkTable entry"
          />
        </div>
      </CardContent>
    </Card>
  );
}
