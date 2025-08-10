"use client";

import { Column, Row } from "@/widgets/containers";
import { CameraCalibrationModule } from "./camera_calibration";
import { background, baseCardColor, teamColor } from "@/services/style";
import { CameraStream } from "@/widgets/cameraStream";
import { Card } from "@/components/ui/card";
import { Placeholder } from "@/widgets/placeholder";
import { useEffect, useState } from "react";
import { useBackendContext } from "@/services/backend/backendContext";
import { CameraProto } from "@/proto/v1/camera";
import { CameraConfigModule } from "./camera_config_module";

export default function CameraConfigPage() {
  const { cameras, socket } = useBackendContext();
  const [selectedCamera, setSelectedCamera] = useState<CameraProto | undefined>(
    cameras.get(0),
  );

  useEffect(() => {
    setSelectedCamera(cameras.get(0));
  }, [cameras]);

  useEffect(() => {
    document.title = "Synapse Client";
  }, []);

  return (
    <div
      className="w-full min-h-screen text-pink-600"
      style={{ backgroundColor: background, color: teamColor, padding: "10px" }}
    >
      <Row className="h-full" gap="gap-2" wrap={true}>
        <Column className="flex-[2] space-y-2 h-full">
          <CameraConfigModule
            cameras={cameras}
            selectedCamera={selectedCamera}
            setSelectedCamera={setSelectedCamera}
            socket={socket}
          />
          {/* <CameraTransformModule /> */}
          <CameraCalibrationModule
            selectedCamera={selectedCamera}
            socket={socket}
          />
        </Column>

        <Column className="flex-auto space-y-2 h-full min-w-[500px]">
          <Card
            className="items-center border-none"
            style={{ backgroundColor: baseCardColor }}
          >
            <CameraStream stream={selectedCamera?.streamPath} />
          </Card>
          <Card
            style={{ backgroundColor: baseCardColor }}
            className="border-none h-[300px]"
          >
            <Placeholder text="TODO: Camera Pose Visualization" />
          </Card>
        </Column>
      </Row>
    </div>
  );
}
