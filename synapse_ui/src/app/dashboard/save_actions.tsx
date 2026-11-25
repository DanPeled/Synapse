import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { baseCardColor, teamColor } from "@/services/style";
import { Column } from "@/widgets/containers";
import { Save, Video, VideoOff } from "lucide-react";
import { ReactNode } from "react";

export function ActionButton({
  icon,
  text,
  onClick,
}: {
  icon: ReactNode;
  text: string;
  onClick?: () => void;
}) {
  return (
    <Button
      variant="outline"
      className="rounded-md cursor-pointer bg-gray-800 hover:bg-gray-700 border-none h-12 shrink-0"
      onClick={onClick}
    >
      <span
        className="flex items-center justify-center gap-2 text-lg"
        style={{ color: teamColor }}
      >
        {icon}
        {text}
      </span>
    </Button>
  );
}

export function SaveActionsDialog({
  save,
  recordingStatus,
  setRecordingStatus,
}: {
  save: () => void;
  recordingStatus: boolean;
  setRecordingStatus: (status: boolean) => void;
}) {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex flex-col self-stretch p-2"
    >
      <CardContent className="flex-1 flex flex-col p-0">
        <Column gap="gap-4" justify="center" className="h-full">
          <ActionButton
            text="Save"
            icon={<Save className="size-5" />}
            onClick={save}
          />
          <ActionButton
            text={recordingStatus ? "Stop Recording" : "Record"}
            icon={
              recordingStatus ? (
                <VideoOff className="size-5" />
              ) : (
                <Video className="size-5" />
              )
            }
            onClick={() => setRecordingStatus(!recordingStatus)}
          />
        </Column>
      </CardContent>
    </Card>
  );
}
