import { Ban, SquarePlus } from "lucide-react";
import { useEffect, useState } from "react";
import AlertDialog from "../alert";
import { Button } from "../button";
import { Column, Row } from "../containers";
import Dropdown from "../dropdown";
import TextInput from "../textInput";
import { useBackendContext } from "../../services/backend/backendContext";

interface Option {
  label: string;
  value: string;
}

interface AddPipelineDialogProps {
  visible: boolean;
  setVisible: (visible: boolean) => void;
  addPipeline: (pipeline: Option) => void;
}

export default function AddPipelineDialog({
  visible,
  setVisible,
  addPipeline,
}: AddPipelineDialogProps) {
  const { pipelineContext } = useBackendContext();
  const [pipelineName, setPipelineName] = useState<string>("New Pipeline");
  const [pipelineIndex, setPipelineIndex] = useState<number>(-1); // TODO: fix pipelineIndex logic
  const [pipelineTypes, setPipelineTypes] = useState<Option[]>([]);

  useEffect(() => {
    if (pipelineContext?.pipelineTypes) {
      setPipelineTypes(
        pipelineContext.pipelineTypes.map((type: string) => ({
          label: type,
          value: type,
        }))
      );
    }
  }, [pipelineContext?.pipelineTypes]);

  const cancelColors = {
    enabledColors: {
      background: "#ab0c0c", // dark red
      color: "white",
      border: "#7a0707",
      hoverBackground: "#8a0808",
      hoverBorder: "#5f0505",
    },
    disabledColors: {
      background: "#5a2a2a",
      color: "#c7bebe",
      border: "#7a3f3f",
    },
  };

  const createColors = {
    enabledColors: {
      background: "#270cab", // dark blue
      color: "white",
      border: "#1a076f",
      hoverBackground: "#1f067f",
      hoverBorder: "#140450",
    },
    disabledColors: {
      background: "#3e3a66",
      color: "#b9b7d1",
      border: "#5a587f",
    },
  };

  const isCreateDisabled = pipelineName.trim() === "";

  return (
    <AlertDialog
      visible={visible}
      onClose={() => setVisible(false)}
      style={{ width: "40%", height: "30%", transform: "translate(0%, -20%)" }}
    >
      <Column>
        <h2 style={{ textAlign: "center", userSelect: "none" }}>
          Add A New Pipeline (ID: #{pipelineIndex})
        </h2>
        <TextInput
          label="Pipeline Name"
          onChange={(val: string) => setPipelineName(val)}
          initialValue={pipelineName}
        />
        <Dropdown label="Pipeline Type" options={pipelineTypes} />
        <Row style={{ marginTop: 12, gap: 16 }}>
          <Button
            {...cancelColors}
            onClick={() => setVisible(false)}
            style={{ minWidth: 100 }}
          >
            <span
              style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
            >
              <Ban /> Cancel
            </span>
          </Button>

          <Button
            {...createColors}
            disabled={isCreateDisabled}
            onClick={() => {
              addPipeline({ label: pipelineName, value: pipelineName });
              setVisible(false);
            }}
            style={{ minWidth: 100 }}
          >
            <span
              style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
            >
              <SquarePlus /> Create
            </span>
          </Button>
        </Row>
      </Column>
    </AlertDialog>
  );
}
