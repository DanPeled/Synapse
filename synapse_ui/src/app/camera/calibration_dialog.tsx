import { Button } from "@/components/ui/button";
import { SettingValueProto } from "@/proto/settings/v1/value";
import { CalibrationDataProto, CameraProto } from "@/proto/v1/camera";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import {
  PipelineProto,
  PipelineTypeProto,
  SetPipelineIndexMessageProto,
  SetPipleineSettingMessageProto,
} from "@/proto/v1/pipeline";
import {
  hasSettingValue,
  useBackendContext,
} from "@/services/backend/backendContext";
import {
  GenerateControl,
  settingValueToProto,
} from "@/services/controls_generator";
import { teamColor } from "@/services/style";
import { WebSocketWrapper } from "@/services/websocket";
import { AlertDialog } from "@/widgets/alertDialog";
import { CameraStream } from "@/widgets/cameraStream";
import { Column, Row } from "@/widgets/containers";
import { Barcode, Camera, LoaderPinwheel, X } from "lucide-react";
import { JSX, useEffect, useState } from "react";

function setCalibrationPipeline(
  socket?: WebSocketWrapper,
  camera?: CameraProto,
) {
  if (camera) {
    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
      pipelineInfo: PipelineProto.create({
        name: "TemporaryCalibrationPipeline",
        type: "$$CalibrationPipeline$$",
        index: 9999,
        settingsValues: {},
      }),
    });

    const binary = MessageProto.encode(payload).finish();
    socket?.sendBinary(binary);

    const setPipelinePayload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX,
      setPipelineIndex: SetPipelineIndexMessageProto.create({
        cameraIndex: camera.index,
        pipelineIndex: 9999,
      }),
    });

    const setPipelineBinary = MessageProto.encode(setPipelinePayload).finish();
    socket?.sendBinary(setPipelineBinary);
  }
}

export function CalibrationDialog({
  visible,
  setVisible,
  initialResolution,
  camera,
  socket,
}: {
  visible: boolean;
  setVisible: (visible: boolean) => void;
  initialResolution?: string;
  camera?: CameraProto;
  socket?: WebSocketWrapper;
}) {
  const [prevPipelineIndex, setPrevPipelineIndex] = useState<
    number | undefined
  >(undefined);

  const [cameraControls, setCameraControls] = useState<
    (JSX.Element | undefined)[]
  >([]);
  const [pipelineControls, setPipelineControls] = useState<
    (JSX.Element | undefined)[]
  >([]);

  const [selectedPipelineType, setSelectedPipelineType] = useState<
    PipelineTypeProto | undefined
  >(undefined);
  const [selectedPipeline, setSelectedPipeline] = useState<
    PipelineProto | undefined
  >(undefined);

  const [resolutonCalibrationData, setResolutionCalibrationData] = useState<
    CalibrationDataProto | undefined
  >();

  const {
    stateRef,
    calibrationdata,
    calibrating,
    pipelines,
    pipelinetypes,
    connection,
    setPipelines,
  } = useBackendContext();

  useEffect(() => {
    if (camera) {
      const cameraCalibrations = calibrationdata.get(camera.index);
      cameraCalibrations?.forEach((calib) => {
        if (
          calib.resolution ==
          selectedPipeline?.settingsValues["resolution"].stringValue
        ) {
          setResolutionCalibrationData(calib);
        }
      });
    }
  }, [calibrationdata]);

  useEffect(() => {
    generateControls();
  }, [selectedPipelineType, selectedPipeline]);

  useEffect(() => {
    if (visible) {
      const pipelineIndex = 9999;
      const pipeline = pipelines.get(pipelineIndex);

      if (pipeline) {
        setSelectedPipeline(pipeline);

        const type = pipelinetypes.get("$$CalibrationPipeline$$");
        if (type) {
          setSelectedPipelineType(type);
        } else {
          console.warn("Pipeline type not found for", pipeline.type);
        }
      } else {
        console.warn("No valid pipeline found for camera", camera);
      }
    }
  }, [pipelines, pipelinetypes, camera, visible]);

  function setSetting(
    val: SettingValueProto,
    setting: string,
    pipeline?: PipelineProto,
    socket?: WebSocketWrapper,
  ) {
    if (!pipeline) {
      pipeline = pipelines.get(9999);
    }

    if (pipeline !== undefined) {
      if (hasSettingValue(val)) {
        const payload = MessageProto.create({
          type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_SETTING,
          setPipelineSetting: SetPipleineSettingMessageProto.create({
            pipelineIndex: 9999,
            value: val,
            setting: setting,
          }),
        });

        const binary = MessageProto.encode(payload).finish();
        socket?.sendBinary(binary);
      }
    }
  }

  function generateControls() {
    if (!selectedPipelineType || !connection.backend) {
      setCameraControls([]);
      setPipelineControls([]);
      return;
    }

    const cameraItems: (JSX.Element | undefined)[] = [];
    const pipelineItems: (JSX.Element | undefined)[] = [];

    selectedPipelineType.settings.forEach((setting) => {
      const control = (
        <GenerateControl
          key={setting.name + setting.category}
          setting={setting}
          setValue={(val) => {
            if (hasSettingValue(val)) {
              setTimeout(() => {
                if (selectedPipeline) {
                  const oldPipelines = pipelines;

                  const newSettingsValues = {
                    ...selectedPipeline.settingsValues,
                    [setting.name]: val,
                  };

                  const updatedPipeline = {
                    ...selectedPipeline,
                    settingsValues: newSettingsValues,
                  };

                  const newPipelines = new Map(oldPipelines);
                  newPipelines.set(selectedPipeline.index, updatedPipeline);
                  // setPipelines(newPipelines);

                  if (stateRef) {
                    stateRef.current.pipelines = newPipelines;
                  }
                }
              }, 10);

              setTimeout(() => {
                setSetting(val, setting.name, selectedPipeline, socket);
              }, 10);
            }
          }}
          value={
            selectedPipeline?.settingsValues[setting.name] ??
            setting.default ??
            settingValueToProto("")
          }
          defaultValue={setting.default}
          locked={false}
        />
      );

      if (setting.category === "Camera Properties") {
        cameraItems.push(control);
      } else {
        pipelineItems.push(control);
      }
    });

    setCameraControls(cameraItems);
    setPipelineControls(pipelineItems);
  }

  useEffect(() => {
    if (visible) {
      if (camera) {
        generateControls();
        if (camera.pipelineIndex !== 9999) {
          setPrevPipelineIndex(camera.pipelineIndex);
        }
        setCalibrationPipeline(socket, camera);
      }
    }
  }, [visible]);

  useEffect(() => {
    setSelectedPipelineType(pipelinetypes.get("$$CalibrationPipeline$$"));
    setSelectedPipeline(pipelines.get(9999));
    generateControls();
  }, [pipelines, visible, camera]);

  return (
    <AlertDialog
      visible={visible}
      onClose={() => {
        setVisible(false);
      }}
      className="w-[90vw] h-[90vh]"
    >
      <div style={{ color: teamColor }}>
        <Button
          onClick={() => {
            if (
              visible &&
              camera &&
              camera.pipelineIndex !== prevPipelineIndex
            ) {
              const setPipelinePayload = MessageProto.create({
                type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX,
                setPipelineIndex: SetPipelineIndexMessageProto.create({
                  cameraIndex: camera.index,
                  pipelineIndex: prevPipelineIndex,
                }),
              });

              const setPipelineBinary =
                MessageProto.encode(setPipelinePayload).finish();
              socket?.sendBinary(setPipelineBinary);

              const deletePipelinePayload = MessageProto.create({
                type: MessageTypeProto.MESSAGE_TYPE_PROTO_DELETE_PIPELINE,
                removePipelineIndex: 9999,
              });

              const removePipelineBinary = MessageProto.encode(
                deletePipelinePayload,
              ).finish();

              socket?.sendBinary(removePipelineBinary);
            }

            setVisible(false);
          }}
          className="w-auto cursor-pointer hover:bg-zinc-600 bg-zinc-700"
          style={{ color: teamColor }}
        >
          <span className="flex items-center justify-center gap-2">
            <X />
            Close
          </span>
        </Button>
      </div>

      <Row className="mt-4 w-full" gap="gap-10" style={{ color: teamColor }}>
        <Column className="flex-1" style={{ color: teamColor }}>
          <h1 className="text-xl" style={{ color: teamColor }}>
            Camera #{camera?.index} Config:
          </h1>
          {!calibrating ? (
            cameraControls.length > 0 ? (
              <div className="space-y-2 pr-4">{cameraControls}</div>
            ) : (
              <div className="text-center" style={{ color: teamColor }}>
                <Camera className="w-16 h-16 mx-auto mb-2 opacity-50" />
                <p className="select-none">Camera Settings</p>
                <p className="text-sm select-none">
                  Configure camera parameters
                </p>
              </div>
            )
          ) : undefined}
          <div className="items-center">
            {calibrating ? (
              <LoaderPinwheel className="w-16 h-16" color={teamColor} />
            ) : camera ? (
              <p></p>
            ) : undefined}
          </div>
        </Column>

        <Column className="flex-1 items-center space-y-10">
          <CameraStream stream={camera?.streamPath} maxWidth="max-w-[500px]" />
          {!calibrating ? (
            pipelineControls.length > 0 ? (
              <div className="space-y-2">{pipelineControls}</div>
            ) : (
              <div
                className="text-center items-center"
                style={{ color: teamColor }}
              >
                <Barcode className="w-16 h-16 mx-auto mb-2 opacity-50" />
                <p className="select-none">Calibration Settings</p>
                <p className="text-sm select-none">
                  Configure calibration parameters
                </p>
              </div>
            )
          ) : undefined}
        </Column>
      </Row>
    </AlertDialog>
  );
}
