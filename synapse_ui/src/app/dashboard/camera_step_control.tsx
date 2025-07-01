import { Card } from "@/components/ui/card";
import { baseCardColor, teamColor } from "@/services/style";
import { Button } from "@/widgets/button";
import { Row } from "@/widgets/containers";
import { Camera, ScanEye } from "lucide-react";

export function CameraStepControl({ }) {
  return (
    <Card
      style={{ backgroundColor: baseCardColor, color: teamColor }}
      className="border-gray-700 flex flex-col h-full max-h-[400px] p-2 spacing-y-0"
    >
      <div>
        <h3 className="items-center text-center pb-0">Stream Display</h3>
        <Row className="flex w-full gap-2">
          <Button className="flex flex-1 items-center justify-center gap-2">
            <Camera className="w-4 h-4" />
            Raw
          </Button>
          <Button className="flex flex-1 items-center justify-center gap-2">
            <ScanEye className="w-4 h-4" />
            Processed
          </Button>
        </Row>
      </div>
    </Card>
  );
}
