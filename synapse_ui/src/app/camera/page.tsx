"use client";

import { Column, Row } from "@/widgets/containers";
import { CameraCalibrationModule } from "./camera_calibration";
import { background, baseCardColor, teamColor } from "@/services/style";
import { CameraStream } from "@/widgets/cameraStream";
import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { useBackendContext } from "@/services/backend/backendContext";
import { CameraProto } from "@/generated/messages/v1/camera";
import { CameraConfigModule } from "./camera_config_module";
import { Badge } from "@/components/ui/badge";
import { Activity } from "lucide-react";

export default function CameraConfigPage() {
  const { cameras, socket, cameraperformance } = useBackendContext();
  const [selectedCamera, setSelectedCamera] = useState<CameraProto | undefined>(
    undefined,
  );
  const [selectedCameraIndex, setSelectedCameraIndex] = useState<number>(0);

  useEffect(() => {
    if (selectedCameraIndex !== undefined) {
      setSelectedCamera(cameras.get(selectedCameraIndex));
    }
  }, [cameras, selectedCameraIndex]);

  useEffect(() => {
    document.title = "Synapse Client";
  }, []);

  const cameraPerformance = cameraperformance?.get(selectedCameraIndex);

  return (
    <div
      className="w-full min-h-screen text-pink-600"
      style={{ backgroundColor: background, color: teamColor, padding: "10px" }}
    >
      <Row className="h-full" gap="gap-2" wrap={true}>
        <Column className="flex-[1.2] space-y-2 h-full">
          <CameraConfigModule
            cameras={cameras}
            selectedCamera={selectedCamera}
            setSelectedCamera={(cam) => setSelectedCameraIndex(cam?.index ?? 0)}
            socket={socket}
          />
          <CameraCalibrationModule
            selectedCamera={selectedCamera}
            socket={socket}
          />
        </Column>

        <Column className="flex-auto space-y-1">
          <Card
            className="h-full border-none"
            style={{ backgroundColor: baseCardColor }}
          >
            <CameraStream stream={selectedCamera?.streamPath} />
            <div className="flex justify-end p-0.2 pr-2 space-y-2">
              <Badge
                variant="secondary"
                className="bg-stone-700 text-sm"
                style={{ color: teamColor }}
              >
                <Activity className="w-3 h-3 mr-1" />
                Processing @ {cameraPerformance?.fps ?? 0} FPS –{" "}
                {cameraPerformance
                  ? cameraPerformance.latencyProcess.toFixed(2)
                  : "0.00"}
                ms latency
              </Badge>
            </div>
          </Card>
        </Column>
      </Row>
    </div>
  );
}
