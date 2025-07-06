import { Button } from "@/components/ui/button";
import { X, Check } from "lucide-react";
import { teamColor } from "@/services/style";
import { Column } from "@/widgets/containers";
import { PipelineTypeProto } from "@/proto/v1/pipeline";
import { AlertDialog } from "@/widgets/alertDialog";

export function ChangePipelineTypeDialog({
  visible,
  setVisible,
  requestedType,
  currentType,
  setPipelineType,
}: {
  visible: boolean;
  setVisible: (state: boolean) => void;
  requestedType: PipelineTypeProto | undefined;
  currentType: PipelineTypeProto | undefined;
  setPipelineType: (pipeType: PipelineTypeProto | undefined) => void;
}) {
  return (
    <AlertDialog
      visible={visible}
      onClose={() => setVisible(false)}
      className="w-[40vw] h-[30vh] -translate-y-40"
    >
      <Column gap="gap-2">
        <h1 className="text-center text-3xl" style={{ color: teamColor }}>
          Are you sure you want to switch pipeline type from
          <span className="font-semibold text-blue-300">
            {" "}
            {currentType?.type}{" "}
          </span>
          to
          <span className="font-semibold text-yellow-400">
            {" "}
            {requestedType?.type}{" "}
          </span>
          ?
        </h1>
        <h1 className="text-lg text-center" style={{ color: teamColor }}>
          This action will result in all the current pipeline settings being
          deleted and becoming the defaults for the new pipleine
        </h1>
        <div className="h-4"></div>
        <Button
          variant="outline"
          size="sm"
          className="rounded-md cursor-pointer bg-green-600 hover:bg-green-500 border-none"
          onClick={() => {
            setPipelineType?.(requestedType);
            setVisible(false);
          }}
        >
          <span
            className="flex items-center justify-center gap-2 font-bold"
            style={{ color: "black" }}
          >
            <Check />
            Confirm
          </span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-md cursor-pointer bg-red-600 hover:bg-red-500 border-none"
          onClick={() => setVisible(false)}
        >
          <span
            className="flex items-center justify-center gap-2"
            style={{ color: "black" }}
          >
            <X />
            Cancel
          </span>
        </Button>
      </Column>
    </AlertDialog>
  );
}
