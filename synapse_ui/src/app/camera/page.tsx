"use client";

import { Column, Row } from "@/widgets/containers";
import { CameraCalibrationModule } from "./camera_calibration";
import { background, baseCardColor, teamColor } from "@/services/style";
import { CameraStream } from "@/widgets/cameraStream";
import { Card } from "@/components/ui/card";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import { Placeholder } from "@/widgets/placeholder";
import { CameraTransformModule } from "./camera_transform";

export default function CameraConfigPage() {
  return (
    <div
      className="w-full min-h-screen text-pink-600"
      style={{ backgroundColor: background, color: teamColor, padding: "10px" }}
    >
      <Row className="h-full" gap="gap-2" wrap={true}>
        <Column className="flex-[2] space-y-2 h-full">
          <CameraTransformModule />
          <CameraCalibrationModule />
        </Column>

        <Column className="flex-auto space-y-2 h-full min-w-[500px]">
          <Card
            className="items-center border-none"
            style={{ backgroundColor: baseCardColor }}
          >
            <Dropdown
              options={[] as DropdownOption<string>[]}
              label="Camera"
              value={""}
              onValueChange={(_) => {
                /* TODO */
              }}
            />
            <CameraStream />
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
