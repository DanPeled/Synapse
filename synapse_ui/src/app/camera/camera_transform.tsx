import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Move3D } from "lucide-react";
import { baseCardColor, teamColor } from "@/services/style";
import { Placeholder } from "@/widgets/placeholder";
import { Column, Row } from "@/widgets/containers";
import TextInput from "@/widgets/textInput";
import { Button } from "@/components/ui/button";

export function CameraTransformModule({}) {
  return (
    <Card
      className="border-none"
      style={{ backgroundColor: baseCardColor, color: teamColor }}
    >
      <CardHeader className="pb-0">
        <div className="flex items-center gap-2">
          <Move3D className="w-5 h-5" />
          <CardTitle className="text-lg font-bold">Camera Transform</CardTitle>
        </div>
        <CardDescription>
          Defines the camera’s position and orientation relative to the robot in
          3D space.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Column gap="gap-2">
          <h3>Camera Position</h3>
          <Row>
            <TextInput label="Forward (m)" labelColor="red" />
            <TextInput label="Left (m)" labelColor="green" />
            <TextInput label="Up (m)" labelColor="blue" />
          </Row>
          <div className="h-5" />
          <h3>Camera Rotation</h3>
          <Row>
            <TextInput label="Roll (deg CCW)" labelColor="red" />
            <TextInput label="Pitch (deg CCW)" labelColor="green" />
            <TextInput label="Yaw (deg CCW)" labelColor="blue" />
          </Row>
          <div className="h-7" />
          <Button
            variant="outline"
            size="sm"
            className="ml-4 border-gray-600 bg-gray-700 hover:bg-gray-600 hover:border-gray-500 cursor-pointer"
            style={{ color: teamColor }}
          >
            Save To Disk
          </Button>
        </Column>
      </CardContent>
    </Card>
  );
}
