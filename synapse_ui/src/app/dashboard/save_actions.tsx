import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { baseCardColor, teamColor } from "@/services/style";
import { Row } from "@/widgets/containers";
import { Lock, Save, Unlock } from "lucide-react";
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
      className="rounded-md cursor-pointer bg-gray-800 hover:bg-gray-700 border-none h-full"
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
  locked,
  setLocked,
  save,
}: {
  locked: boolean;
  setLocked: (locked: boolean) => void;
  save: () => void;
}) {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 flex flex-col h-full p-2"
    >
      <CardContent>
        <Row gap="gap-4" justify="center">
          <ActionButton
            text="Save"
            icon={<Save className="size-10" />}
            onClick={save}
          />
          {locked ? (
            <ActionButton
              text="Unlock"
              icon={<Unlock className="size-10" />}
              onClick={() => setLocked(false)}
            />
          ) : (
            <ActionButton
              text="Lock"
              icon={<Lock className="size-10" />}
              onClick={() => setLocked(true)}
            />
          )}
        </Row>
      </CardContent>
    </Card>
  );
}
