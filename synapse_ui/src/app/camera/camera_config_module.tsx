import { Fragment, JSX, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { CameraProto, RenameCameraMessageProto } from "@/proto/v1/camera";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { CameraID } from "@/services/backend/dataStractures";
import { baseCardColor, borderColor, teamColor } from "@/services/style";
import { WebSocketWrapper } from "@/services/websocket";
import { Row } from "@/widgets/containers";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import TextInput from "@/widgets/textInput";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@radix-ui/react-dropdown-menu";
import {
  Ban,
  Check,
  Edit,
  MoreVertical,
  Trash,
  Camera,
  Hash,
  Sliders,
  PlayCircle,
  Activity,
} from "lucide-react";
import { useBackendContext } from "@/services/backend/backendContext";

export function CameraConfigModule({
  cameras,
  selectedCamera,
  setSelectedCamera,
  socket,
}: {
  cameras: Map<CameraID, CameraProto>;
  selectedCamera?: CameraProto;
  setSelectedCamera: (cam?: CameraProto) => void;
  socket?: WebSocketWrapper;
}) {
  const [isRenaming, setIsRenaming] = useState(false);
  const [newName, setNewName] = useState(selectedCamera?.name ?? "");
  const { pipelines } = useBackendContext();

  useEffect(() => {
    setNewName(selectedCamera?.name ?? "");
  }, [selectedCamera]);

  /* ---------- derived data ---------- */

  const cameraOptions: DropdownOption<CameraProto>[] = Array.from(
    cameras.values(),
  ).map((cam) => ({
    label: cam.name,
    value: cam,
  }));

  const infoFields: [string, string][] = [
    ["Camera Index", `#${selectedCamera?.index ?? "—"}`],
    ["Device UID", selectedCamera?.kind ?? "—"],
    ["Stream Path", selectedCamera?.streamPath ?? "—"],
    [
      "Default Pipeline",
      selectedCamera
        ? `#${selectedCamera.defaultPipeline} (${
            (selectedCamera &&
              pipelines
                .get(selectedCamera.index)
                ?.get(selectedCamera.defaultPipeline)?.name) ??
            "Unknown"
          })`
        : "N/A",
    ],
    ["Max FPS", selectedCamera?.maxFps.toString() ?? "—"],
  ];

  /* ---------- actions ---------- */

  const handleRenameSubmit = () => {
    if (!selectedCamera) return;

    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_RENAME_CAMERA,
      renameCamera: RenameCameraMessageProto.create({
        cameraIndex: selectedCamera.index,
        newName,
      }),
    });

    socket?.sendBinary(MessageProto.encode(payload).finish());
    setIsRenaming(false);
  };

  const handleRenameCancel = () => {
    setIsRenaming(false);
    setNewName(selectedCamera?.name ?? "");
  };

  /* ---------- shared styles ---------- */

  const baseButtonClass = "bg-zinc-900 hover:bg-zinc-800 border rounded-md";
  const buttonStyle = {
    borderColor,
    color: teamColor,
  };

  /* ---------- render ---------- */

  return (
    <Card
      className="rounded-xl border shadow-sm"
      style={{
        backgroundColor: baseCardColor,
        color: teamColor,
        borderColor,
      }}
    >
      <CardHeader className="pb-2">
        <div className="text-lg font-semibold">Camera Configuration</div>
        <CardDescription className="text-xs opacity-70">
          Manage camera settings and properties
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        {isRenaming ? (
          <RenameSection
            newName={newName}
            setNewName={setNewName}
            onCancel={handleRenameCancel}
            onSubmit={handleRenameSubmit}
            buttonClass={baseButtonClass}
            buttonStyle={buttonStyle}
          />
        ) : (
          <TopControls
            options={cameraOptions}
            selectedCamera={selectedCamera}
            setSelectedCamera={setSelectedCamera}
            onRename={() => setIsRenaming(true)}
          />
        )}

        <InfoGrid fields={infoFields} />
      </CardContent>
    </Card>
  );
}

function TopControls({
  options,
  selectedCamera,
  setSelectedCamera,
  onRename,
}: {
  options: DropdownOption<CameraProto>[];
  selectedCamera?: CameraProto;
  setSelectedCamera: (cam?: CameraProto) => void;
  onRename: () => void;
}) {
  return (
    <Row className="items-center gap-4">
      <Dropdown
        className="min-w-100 w-auto"
        options={options}
        label="Camera"
        value={selectedCamera}
        onValueChange={(cam) => cam && setSelectedCamera(cam)}
      />

      <CameraActions
        selectedCamera={selectedCamera}
        setRenamingCamera={onRename}
      />
    </Row>
  );
}

/* ---------- Rename ---------- */

function RenameSection({
  newName,
  setNewName,
  onCancel,
  onSubmit,
  buttonClass,
  buttonStyle,
}: {
  newName: string;
  setNewName: (v: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
  buttonClass: string;
  buttonStyle: React.CSSProperties;
}) {
  return (
    <Row className="items-end gap-3">
      <TextInput
        label="Camera Name"
        inputWidth="w-64"
        value={newName}
        onChange={setNewName}
      />

      <Button
        variant="outline"
        className={buttonClass}
        style={buttonStyle}
        onClick={onCancel}
      >
        <Ban className="w-4 h-4" />
      </Button>

      <Button
        variant="outline"
        className={buttonClass}
        style={buttonStyle}
        onClick={onSubmit}
      >
        <Check className="w-4 h-4" />
      </Button>
    </Row>
  );
}

/* ---------- Info Grid ---------- */

const fieldIcons: Record<string, JSX.Element> = {
  "Camera Index": <Hash className="w-4 h-4 opacity-70 mr-1" />,
  "Device UID": <Camera className="w-4 h-4 opacity-70 mr-1" />,
  "Stream Path": <PlayCircle className="w-4 h-4 opacity-70 mr-1" />,
  "Default Pipeline": <Sliders className="w-4 h-4 opacity-70 mr-1" />,
  "Max FPS": <Activity className="w-4 h-4 opacity-70 mr-1" />,
};

function InfoGrid({ fields }: { fields: [string, string][] }) {
  return (
    <div className="grid grid-cols-2 gap-x-0 gap-y-2 text-sm">
      {fields.map(([label, value]) => (
        <Fragment key={label}>
          <span className="font-medium flex items-center opacity-70">
            {fieldIcons[label]}
            {label}
          </span>
          <span className="truncate">
            {label === "Stream Path" && value !== "—" ? (
              <a href={value} className="underline hover:opacity-80">
                {value}
              </a>
            ) : (
              value
            )}
          </span>
        </Fragment>
      ))}
    </div>
  );
}

/* ---------- Actions ---------- */

function CameraActions({
  selectedCamera,
  setRenamingCamera,
}: {
  selectedCamera?: CameraProto;
  setRenamingCamera: () => void;
}) {
  const actions = [
    {
      icon: <Edit className="w-4 h-4" />,
      label: "Rename",
      onClick: setRenamingCamera,
      disabled: !selectedCamera,
    },
    {
      icon: <Trash className="w-4 h-4" />,
      label: "Remove Camera",
      onClick: () => {},
      disabled: true,
    },
  ];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className="bg-zinc-900 hover:bg-zinc-800 border rounded-md"
          style={{ borderColor, color: teamColor }}
        >
          <MoreVertical className="w-4 h-4" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        className="rounded-lg bg-zinc-800 border shadow-md p-1"
        style={{ borderColor }}
      >
        {actions.map(({ icon, label, onClick, disabled }) => (
          <DropdownMenuItem
            key={label}
            disabled={disabled}
            onClick={onClick}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm
              ${
                disabled
                  ? "opacity-40 cursor-not-allowed"
                  : "hover:bg-zinc-700 cursor-pointer"
              }
            `}
            style={{ color: teamColor }}
          >
            {icon}
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
