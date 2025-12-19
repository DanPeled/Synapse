import { Button } from "@/components/ui/button";
import { SettingValueProto } from "@/proto/settings/v1/value";
import { CalibrationDataProto, CameraProto } from "@/proto/v1/camera";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import {
  PipelineProto,
  PipelineTypeProto,
  RemovePipelineMessageProto,
  SetPipelineIndexMessageProto,
  SetPipleineSettingMessageProto,
} from "@/proto/v1/pipeline";
import {
  hasSettingValue,
  useBackendContext,
} from "@/services/backend/backendContext";
import { PipelineID } from "@/services/backend/dataStractures";
import {
  GenerateControl,
  generateControlFromSettingMeta,
  settingValueToProto,
} from "@/services/controls_generator";
import { baseCardColor, teamColor } from "@/services/style";
import { WebSocketWrapper } from "@/services/websocket";
import { AlertDialog } from "@/widgets/alertDialog";
import { CameraStream } from "@/widgets/cameraStream";
import { Column, Row } from "@/widgets/containers";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { Barcode, Camera, LoaderPinwheel, Settings, X } from "lucide-react";
import { JSX, useEffect, useRef, useState } from "react";

const CALIBRATION_PIPELINE_ID = 9999;

function setCalibrationPipeline(
  socket: WebSocketWrapper,
  camera?: CameraProto,
) {
  if (camera) {
    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE,
      pipelineInfo: PipelineProto.create({
        name: "TemporaryCalibrationPipeline",
        type: "$$CalibrationPipeline$$",
        index: CALIBRATION_PIPELINE_ID,
        settingsValues: {},
      }),
    });

    const binary = MessageProto.encode(payload).finish();
    socket.sendBinary(binary);

    const setPipelinePayload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX,
      setPipelineIndex: SetPipelineIndexMessageProto.create({
        cameraIndex: camera.index,
        pipelineIndex: CALIBRATION_PIPELINE_ID,
      }),
    });

    const setPipelineBinary = MessageProto.encode(setPipelinePayload).finish();
    socket.sendBinary(setPipelineBinary);
  }
}

export function CalibrationDialog({
  visible,
  setVisible,
  initialResolution,
  camera,
}: {
  visible: boolean;
  setVisible: (visible: boolean) => void;
  initialResolution?: string;
  camera?: CameraProto;
}) {
  const { socket } = useBackendContext();

  const [prevPipelineIndex, setPrevPipelineIndex] = useState<
    number | undefined
  >(undefined);

  const prevCalibratingRef = useRef<boolean>(false);

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
    calibrationdata,
    calibrating,
    pipelines,
    setPipelines,
    pipelinetypes,
    connection,
    cameras,
  } = useBackendContext();

  useEffect(() => {
    if (prevCalibratingRef.current === true && calibrating === false) {
      console.log("Calibration just finished!");
      if (camera !== undefined) {
        close(camera);
      }
    }
    prevCalibratingRef.current = calibrating;
  }, [calibrating]);

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
  }, [selectedPipelineType, selectedPipeline, camera, cameras]);

  useEffect(() => {
    if (visible) {
      const pipelineIndex = CALIBRATION_PIPELINE_ID;
      const pipeline = pipelines.get(camera?.index ?? -1)?.get(pipelineIndex);

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
  ) {
    if (hasSettingValue(val)) {
      const payload = MessageProto.create({
        type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_SETTING,
        setPipelineSetting: SetPipleineSettingMessageProto.create({
          pipelineIndex: pipeline!.index,
          cameraid: camera!.index,
          value: val,
          setting: setting,
        }),
      });
      socket?.sendBinary(MessageProto.encode(payload).finish());
    }
  }

  function setPipelinesOfSelectedCamera(
    newpipelines: Map<PipelineID, PipelineProto>,
  ) {
    if (camera !== undefined) {
      setPipelines((prev) => {
        const copy = new Map(prev);
        copy.set(camera?.index ?? 0, newpipelines);
        return copy;
      });
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

    if (!camera) return;

    selectedPipelineType.settings.forEach((setting) => {
      const control = generateControlFromSettingMeta({
        setting: setting,
        selectedPipeline: selectedPipeline,
        setPipelines: setPipelinesOfSelectedCamera,
        setSetting: setSetting,
        locked: false,
        pipelines: pipelines.get(camera!.index) ?? new Map(),
      });

      if (setting.category === "Camera Properties") {
        cameraItems.push(control);
      } else {
        pipelineItems.push(control);
      }
    });

    camera?.settings.forEach((setting) => {
      const control = generateControlFromSettingMeta({
        setting: setting,
        selectedPipeline: selectedPipeline,
        setPipelines: setPipelinesOfSelectedCamera,
        setSetting: setSetting,
        locked: false,
        pipelines: pipelines.get(camera!.index) ?? new Map(),
      });
      cameraItems.push(control);
    });

    setCameraControls(cameraItems);
    setPipelineControls(pipelineItems);
  }

  useEffect(() => {
    if (socket) {
      if (visible) {
        if (camera) {
          generateControls();
          if (camera.pipelineIndex !== CALIBRATION_PIPELINE_ID) {
            setPrevPipelineIndex(camera.pipelineIndex);
          }
          setCalibrationPipeline(socket, camera);
        }
      }
    }
  }, [visible]);

  useEffect(() => {
    if (calibrating) {
    }
  }, [calibrating]);

  useEffect(() => {
    setSelectedPipelineType(pipelinetypes.get("$$CalibrationPipeline$$"));
    setSelectedPipeline(
      pipelines.get(camera?.index ?? -1)?.get(CALIBRATION_PIPELINE_ID),
    );
    generateControls();
  }, [pipelines, visible, camera]);

  function close(camera: CameraProto) {
    const setPipelinePayload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX,
      setPipelineIndex: SetPipelineIndexMessageProto.create({
        cameraIndex: camera.index,
        pipelineIndex: prevPipelineIndex,
      }),
    });

    const setPipelineBinary = MessageProto.encode(setPipelinePayload).finish();
    socket?.sendBinary(setPipelineBinary);

    const deletePipelinePayload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_DELETE_PIPELINE,
      removePipeline: RemovePipelineMessageProto.create({
        removePipelineIndex: CALIBRATION_PIPELINE_ID,
        cameraid: camera.index,
      }),
    });

    const removePipelineBinary = MessageProto.encode(
      deletePipelinePayload,
    ).finish();

    socket?.sendBinary(removePipelineBinary);

    setVisible(false);
  }

  return (
    <AlertDialog
      visible={visible}
      onClose={() => {
        setVisible(false);
      }}
      className="w-[90vw] h-[90vh]"
    >
      <Row style={{ color: teamColor }} className="items-center">
        <Button
          onClick={() => {
            if (
              visible &&
              camera &&
              camera.pipelineIndex !== prevPipelineIndex
            ) {
              close(camera);
            }
          }}
          className="w-auto cursor-pointer hover:bg-zinc-600 bg-zinc-700"
          style={{ color: teamColor }}
        >
          <span className="flex items-center justify-center gap-2">
            <X />
            Close
          </span>
        </Button>
        <h1 className="text-xl pl-2 text-center" style={{ color: teamColor }}>
          Camera #{camera?.index} Calibration:
        </h1>
      </Row>

      <Row className="mt-4 w-full" gap="gap-2" style={{ color: teamColor }}>
        <Column className="flex-1" style={{ color: teamColor }}>
          <Tabs
            defaultValue="input"
            className="w-full"
            style={{ color: teamColor }}
          >
            <TabsList
              className="grid w-full grid-cols-2 border-gray-600 rounded-xl gap-2"
              style={{ backgroundColor: baseCardColor }}
            >
              <TabsTrigger
                value="input"
                className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer h-8"
              >
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  <span>Camera Properties</span>
                  <Camera />
                </div>
              </TabsTrigger>
              <TabsTrigger
                value="pipeline"
                className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer"
              >
                {selectedPipelineType?.type.replaceAll("$$", "") ?? "Pipeline"}
              </TabsTrigger>
              {/* <TabsTrigger */}
              {/*   value="output" */}
              {/*   className="bg-zinc-800 rounded-md data-[state=active]:bg-pink-800 hover:bg-zinc-700 transition-colors duration-200 cursor-pointer" */}
              {/* > */}
              {/*   Output */}
              {/* </TabsTrigger> */}
            </TabsList>

            <TabsContent value="input" className="p-6 space-y-6">
              <div style={{ color: teamColor }}>
                {cameraControls.length > 0 ? (
                  <div className="space-y-2">{cameraControls}</div>
                ) : (
                  <div className="text-center" style={{ color: teamColor }}>
                    <Camera className="w-16 h-16 mx-auto mb-2 opacity-50" />
                    <p className="select-none">Camera Settings</p>
                    <p className="text-sm select-none">
                      Configure camera parameters
                    </p>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="pipeline" className="p-6 space-y-6">
              <div style={{ color: teamColor }}>
                {pipelineControls.length > 0 ? (
                  <div className="space-y-2">{pipelineControls}</div>
                ) : (
                  <div className="text-center" style={{ color: teamColor }}>
                    <Settings className="w-16 h-16 mx-auto mb-2 opacity-50" />
                    <p className="select-none">Pipeline Settings</p>
                    <p className="text-sm select-none">
                      Configure pipeline-specific parameters
                    </p>
                  </div>
                )}
              </div>
            </TabsContent>

            {/* <TabsContent value="output" className="p-6"> */}
            {/*   <div className="text-center" style={{ color: teamColor }}> */}
            {/*     <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" /> */}
            {/*     <p className="select-none">Output Configuration</p> */}
            {/*     <p className="text-sm select-none"> */}
            {/*       Configure output streams and data */}
            {/*     </p> */}
            {/*   </div> */}
            {/* </TabsContent> */}
          </Tabs>
        </Column>

        <Column className="flex-1 items-center space-y-10">
          <CameraStream stream={camera?.streamPath} maxWidth="max-w-[500px]" />
        </Column>
      </Row>
    </AlertDialog>
  );
}
