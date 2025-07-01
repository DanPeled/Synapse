import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Copy,
  Edit,
  Plus,
  Trash2,
  MoreVertical,
  X,
  Check,
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
import { Column, Row } from "@/widgets/containers";
import { PipelineManagement } from "@/services/backend/pipelineContext";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import ToggleButton from "@/widgets/toggleButtons";
import { Card, CardContent } from "@/components/ui/card";
import { CameraProto } from "@/proto/v1/camera";
import { AlertDialog } from "@/widgets/alertDialog";

function AddPipelineDialog({ visible, setVisible }: { visible: boolean, setVisible: (state: boolean) => void }) {
  return (<AlertDialog
    visible={visible}
    onClose={() => setVisible(false)}
    className="w-[50vw] h-[40vh] -translate-y-40"
  >
    <Button
      variant="outline"
      size="sm"
      className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
      style={{
        borderColor: borderColor,
        color: teamColor,
      }}
      onClick={() => setVisible(false)}
    >
      <span className="flex items-center justify-center gap-2">
        <X />
        Close
      </span>
    </Button>
  </AlertDialog>);
}


function ChangePipelineTypeDialog({ visible, setVisible, requestedType, currentType, setPipelineType }: {
  visible: boolean,
  setVisible: (state: boolean) => void,
  requestedType: PipelineTypeProto | undefined,
  currentType: PipelineTypeProto | undefined,
  setPipelineType: (pipeType: PipelineTypeProto | undefined) => void
}) {
  return (<AlertDialog
    visible={visible}
    onClose={() => setVisible(false)}
    className="w-[40vw] h-[30vh] -translate-y-40"
  >
    <Column gap="gap-2">
      <h1 className="text-center text-3xl" style={{ color: teamColor }}>
        Are you sure you want to switch pipeline type from
        <span className="font-semibold text-blue-300"> {currentType?.type} </span>
        to
        <span className="font-semibold text-yellow-400"> {requestedType?.type} </span>?
      </h1>
      <h1 className="text-lg text-center" style={{ color: teamColor }}>This action will result in all the current pipeline settings being deleted and becoming the defaults for the new pipleine</h1>
      <div className="h-4"></div>
      <Button
        variant="outline"
        size="sm"
        className="rounded-md cursor-pointer bg-green-600 hover:bg-green-500 border-none"
        onClick={() => {
          setPipelineType?.(requestedType);
          setVisible(false);
        }}
      >
        <span className="flex items-center justify-center gap-2 font-bold" style={{ color: "black" }}>
          <Check />
          Confirm
        </span>
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="rounded-md cursor-pointer bg-red-600 hover:bg-red-500 border-none"
        onClick={() => setVisible(false)}
      >
        <span className="flex items-center justify-center gap-2" style={{ color: "black" }}>
          <X />
          Cancel
        </span>
      </Button>
    </Column>
  </AlertDialog>);
}

interface CameraAndPipelineControlsProps {
  pipelinecontext: PipelineManagement.PipelineContext;
  setSelectedPipeline: (val?: PipelineProto) => void;
  selectedPipeline?: PipelineProto;
  selectedPipelineType?: PipelineTypeProto;
  setSelectedPipelineType: (val?: PipelineTypeProto) => void;
  selectedCamera: CameraProto | undefined;
  setSelectedCamera: (cam?: CameraProto) => void;
  cameras: CameraProto[];
}


export function CameraAndPipelineControls({
  pipelinecontext,
  setSelectedPipeline,
  selectedPipeline,
  selectedPipelineType,
  setSelectedPipelineType,
  selectedCamera,
  setSelectedCamera,
  cameras,
}: CameraAndPipelineControlsProps
) {
  const [ignoreNetworkTablePipeline, setIgnoreNetworkTablePipeline] = useState(false);
  const [addPipelineDialogVisible, setAddPipelineDialogVisible] = useState(false);
  const [changePipelineTypeDialogVisible, setChangePipelineTypeDialogVisible] = useState(false);
  const [requestedPipelineType, setRequestedPipelineType] = useState<PipelineTypeProto | undefined>(undefined);

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
            options={
              (cameras ? cameras.map(cam => ({
                label: `${cam.name}`,
                value: cam,
              })) : []) as DropdownOption<CameraProto>[]
            }
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
                  icon: <Edit className="w-4 h-4" style={{ color: teamColor }} />,
                  label: "Rename",
                  action: () => console.log("Rename clicked"),
                },
                {
                  icon: <Plus className="w-4 h-4" style={{ color: teamColor }} />,
                  label: "Add Pipeline",
                  action: () => setAddPipelineDialogVisible(true),
                },
                {
                  icon: <Copy className="w-4 h-4" style={{ color: teamColor }} />,
                  label: "Duplicate",
                  action: () => console.log("Duplicate clicked"),
                },
                {
                  icon: <Trash2 className="w-4 h-4" style={{ color: teamColor }} />,
                  label: "Delete",
                  action: () => console.log("Delete clicked"),
                },
              ].map(({ icon, label, action }) => (
                <DropdownMenuItem
                  key={label}
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
          onValueChange={(val) => {
            setRequestedPipelineType(val);
            setChangePipelineTypeDialogVisible(true);
          }}
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
        <AddPipelineDialog visible={addPipelineDialogVisible} setVisible={setAddPipelineDialogVisible} />
        <ChangePipelineTypeDialog visible={changePipelineTypeDialogVisible}
          setVisible={setChangePipelineTypeDialogVisible}
          requestedType={requestedPipelineType}
          currentType={selectedPipelineType}
          setPipelineType={(val) => {
            setSelectedPipelineType(val);
          }}
        />
      </CardContent>
    </Card >
  );
}
