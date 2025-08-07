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
import {
  baseCardColor,
  borderColor,
  hoverBg,
  teamColor,
} from "@/services/style";
import { WebSocketWrapper } from "@/services/websocket";
import { Column, Row } from "@/widgets/containers";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import TextInput from "@/widgets/textInput";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@radix-ui/react-dropdown-menu";
import assert from "assert";
import { Ban, Check, Edit, MoreVertical, RotateCcw, Trash } from "lucide-react";
import { useEffect, useState } from "react";

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
  const [renameCamera, setRenameCamera] = useState(false);
  const [newCameraName, setNewCameraName] = useState(selectedCamera?.name);

  useEffect(() => {
    if (selectedCamera) {
      setNewCameraName(selectedCamera?.name);
    }
  }, [selectedCamera]);

  return (
    <Card
      className="border-none"
      style={{ backgroundColor: baseCardColor, color: teamColor }}
    >
      <CardHeader className="pb-0">
        <div className="flex items-center gap-2">Camera Configuration</div>
        <CardDescription></CardDescription>
      </CardHeader>
      <CardContent>
        <Row gap="gap-8" className="items-center">
          {renameCamera ? (
            <Row gap="gap-4" className="items-center">
              <TextInput
                label="Camera Name"
                inputWidth="w-100"
                value={newCameraName ?? "Unknown Camera"}
                onChange={setNewCameraName}
              ></TextInput>
              <Button
                variant="outline"
                className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                style={{
                  borderColor: borderColor,
                  color: teamColor,
                }}
                onClick={() => {
                  setRenameCamera(false);
                  setNewCameraName(selectedCamera?.name);
                }}
              >
                <Ban />
              </Button>
              <Button
                variant="outline"
                className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
                style={{
                  borderColor: borderColor,
                  color: teamColor,
                }}
                onClick={() => {
                  assert(selectedCamera !== undefined);

                  const payload = MessageProto.create({
                    type: MessageTypeProto.MESSAGE_TYPE_PROTO_RENAME_CAMERA,
                    renameCamera: RenameCameraMessageProto.create({
                      cameraIndex: selectedCamera?.index,
                      newName: newCameraName,
                    }),
                  });

                  const binary = MessageProto.encode(payload).finish();
                  socket?.sendBinary(binary);

                  setRenameCamera(false);
                  setNewCameraName(selectedCamera?.name);
                }}
              >
                <Check />
              </Button>
            </Row>
          ) : (
            <>
              <Dropdown
                options={
                  (cameras
                    ? Array.from(cameras.values()).map((cam: CameraProto) => ({
                        label: `${cam?.name}`,
                        value: cam,
                      }))
                    : []) as DropdownOption<CameraProto>[]
                }
                label="Camera"
                value={selectedCamera}
                onValueChange={(camera) => {
                  setSelectedCamera(camera);
                }}
              />
              <CameraActions
                selectedCamera={selectedCamera}
                setRenamingCamera={() => {
                  setRenameCamera(true);
                }}
              />
            </>
          )}
        </Row>
        <div className="grid grid-cols-2 gap-y-2 gap-x-4 mt-4 text-sm">
          <span className="font-semibold">Camera Index:</span>
          <span>#{selectedCamera?.index ?? "—"}</span>

          <span className="font-semibold">Camera Device Name:</span>
          <span>{selectedCamera?.kind ?? "—"}</span>

          <span className="font-semibold">Stream Path:</span>
          <span className="hover:text-pink-800 underline">
            <a href={selectedCamera?.streamPath}>
              {selectedCamera?.streamPath ?? "—"}
            </a>
          </span>

          <span className="font-semibold">Default Pipeline:</span>
          <span>{selectedCamera?.defaultPipeline ?? "—"}</span>

          <span className="font-semibold">Max FPS:</span>
          <span>{selectedCamera?.maxFps ?? "—"}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function CameraActions({
  selectedCamera,
  setRenamingCamera,
}: {
  selectedCamera?: CameraProto;
  setRenamingCamera: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className="rounded-md cursor-pointer bg-zinc-900 hover:bg-zinc-700"
          style={{
            borderColor: borderColor,
            color: teamColor,
          }}
        >
          <MoreVertical className="w-4 h-4" style={{ color: teamColor }} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="bottom"
        align="end"
        alignOffset={20}
        className="rounded-md shadow-lg bg-zinc-800"
        style={{
          borderColor: borderColor,
          borderWidth: "1px",
        }}
      >
        {[
          {
            icon: <Edit className="w-5 h-5" style={{ color: teamColor }} />,
            label: "Rename",
            action: setRenamingCamera,
            disabled: () => selectedCamera === undefined,
          },
          {
            icon: <Trash className="w-5 h-5" style={{ color: teamColor }} />,
            label: "Remove Camera",
            action: () => {},
            disabled: () => true,
          },
          {
            icon: (
              <RotateCcw className="w-5 h-5" style={{ color: teamColor }} />
            ),
            label: "Rescan Cameras",
            action: () => {},
            disabled: () => selectedCamera === undefined,
          },
        ].map(({ icon, label, action, disabled }) => (
          <DropdownMenuItem
            key={label}
            disabled={disabled()}
            className={`flex items-center gap-2 text-sm font-medium px-3 py-2 rounded-md ${
              disabled() ? "cursor-not-allowed opacity-50" : "cursor-pointer"
            }`}
            style={{
              color: disabled() ? "#999" : teamColor,
              transition: "all 0.15s ease",
            }}
            onClick={action}
            onMouseEnter={(e) => {
              if (!disabled()) e.currentTarget.style.backgroundColor = hoverBg;
            }}
            onMouseLeave={(e) => {
              if (!disabled())
                e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            {icon}
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
