import { Button } from "@/widgets/button";
import { Import } from "lucide-react";
import { iconSize } from "@/services/style";
import { useFilePicker } from "@/services/useFilePicker";
import {
  uploadFileReplace,
  uploadZipReplaceFolder,
} from "@/services/backend/fileServer";
import { DeviceInfoProto } from "@/proto/v1/device";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { WebSocketWrapper } from "@/services/websocket";
import { useEffect, useRef } from "react";

function ImportSettingsButton({
  deviceinfo,
  socket,
}: {
  deviceinfo: DeviceInfoProto;
  socket?: WebSocketWrapper;
}) {
  const socketRef = useRef(socket);
  useEffect(() => {
    socketRef.current = socket;
  }, [socket]);

  const picker = useFilePicker(async (file) => {
    if (file.name.endsWith(".zip")) {
      if (
        !confirm(
          "Replace the entire config folder on the device?\nThis will delete the existing folder.",
        )
      )
        return;

      await uploadZipReplaceFolder(deviceinfo, file, "config");

      const payload = MessageProto.create({
        type: MessageTypeProto.MESSAGE_TYPE_PROTO_RESTART_SYNAPSE,
      });

      const binary = MessageProto.encode(payload).finish();

      if (!socketRef.current) {
        console.error("Socket not connected");
        return;
      }

      socketRef.current.sendBinary(binary);
      console.log(socket);

      alert("Config folder replaced successfully.");
      return;
    }

    alert("Please select a JSON settings file or a ZIP folder.");
    return;
  }, ".json,.zip");

  return (
    <>
      {picker.input}
      <Button
        className="w-full"
        onClickAction={() => {
          picker.open();
        }}
      >
        <span className="flex items-center justify-center gap-2">
          <Import size={iconSize} />
          Import Settings
        </span>
      </Button>
    </>
  );
}

export default ImportSettingsButton;
