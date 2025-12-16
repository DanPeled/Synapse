"use client";

import React, {
  createContext,
  useContext,
  useReducer,
  ReactNode,
  useEffect,
  useRef,
} from "react";
import { BackendStateSystem } from "./dataStractures";
import {
  DeviceInfoProto,
  HardwareMetricsProto,
  SetNetworkSettingsProto,
} from "@/proto/v1/device";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { WebSocketWrapper } from "../websocket";
import { formatHHMMSSLocal } from "../timeUtil";
import {
  PipelineProto,
  PipelineTypeProto,
  SetPipelineNameMessageProto,
} from "@/proto/v1/pipeline";
import { CameraProto } from "@/proto/v1/camera";
import { SettingValueProto } from "@/proto/settings/v1/value";
import { LogMessageProto } from "@/proto/v1/log";
import assert from "assert";
import { toast } from "sonner";
import { teamColor } from "../style";
import { AlertTypeProto } from "@/proto/v1/alert";

export function hasSettingValue(val: SettingValueProto): boolean {
  return (
    val.intValue !== undefined ||
    val.stringValue !== undefined ||
    val.boolValue !== undefined ||
    val.floatValue !== undefined ||
    val.bytesValue !== undefined ||
    (val.intArrayValue && val.intArrayValue.length > 0) ||
    (val.stringArrayValue && val.stringArrayValue.length > 0) ||
    (val.boolArrayValue && val.boolArrayValue.length > 0) ||
    (val.floatArrayValue && val.floatArrayValue.length > 0) ||
    (val.bytesArrayValue && val.bytesArrayValue.length > 0)
  );
}

const initialState: BackendStateSystem.State = {
  pipelines: new Map(),
  pipelinetypes: new Map(),
  deviceinfo: {
    version: "Unknown",
    hostname: "Unknown",
    ip: "127.0.0.1",
    platform: "Unknown",
    networkInterfaces: [],
  },
  stateRef: undefined,
  hardwaremetrics: {
    cpuTemp: 0,
    cpuUsage: 0,
    diskUsage: 0,
    ramUsage: 0,
    uptime: 0,
    memory: 1,
    lastFetched: "---",
  },
  connection: {
    backend: false,
    networktables: false,
  },
  logs: [],
  cameras: new Map(),
  cameraperformance: new Map(),
  calibrationdata: new Map(),
  recordingstatuses: new Map(),
  pipelineresults: new Map(),
  calibrating: false,
  networksettings: SetNetworkSettingsProto.create({
    teamNumber: 0,
    hostname: "hostname",
    ip: "localhost",
    networkInterface: "interface",
    networkTable: "Synapse",
  }),
};

export const BackendStateKeys = Object.keys(initialState).reduce(
  (acc, key) => {
    acc[key] = key;
    return acc;
  },
  {} as { [key: string]: string },
);

// Reducer function with typed state and action
function reducer(
  state: BackendStateSystem.State,
  action: BackendStateSystem.StateAction,
): BackendStateSystem.State {
  if (action.type.startsWith("SET_")) {
    const key = action.type
      .slice(4)
      .toLowerCase() as keyof BackendStateSystem.State;
    if (key in state) {
      return { ...state, [key]: action.payload };
    }
  }
  return state;
}

// Create the context with a default undefined value
const BackendContextContext = createContext<
  BackendStateSystem.BackendContextType | undefined
>(undefined);

// Props type for the provider
interface BackendContextProviderProps {
  children: ReactNode;
  onChange?: (
    key: keyof BackendStateSystem.State,
    value: BackendStateSystem.State[keyof BackendStateSystem.State],
  ) => void;
}

export const BackendContextProvider: React.FC<BackendContextProviderProps> = ({
  children,
}) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const stateRef = useRef<BackendStateSystem.State>(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // Create setters that both dispatch to the reducer and mirror into stateRef
  const setters = React.useMemo(() => {
    return Object.keys(initialState).reduce((acc, key) => {
      const functionName =
        `set${key.charAt(0).toUpperCase()}${key.slice(1)}` as keyof BackendStateSystem.StateSetter;

      acc[functionName] = (value: unknown | ((prev: unknown) => unknown)) => {
        const keyLower = key.toLowerCase() as keyof BackendStateSystem.State;

        if (typeof value === "function") {
          // compute new value using current state slice
          const currentSlice = state[keyLower];
          const newValue = (value as Function)(currentSlice);

          dispatch({ type: `SET_${key.toUpperCase()}`, payload: newValue });

          // Mirror into the ref immediately so any async handlers see it
          if (stateRef && stateRef.current) {
            // clone Maps/Objects where helpful to avoid accidental mutations
            if (newValue instanceof Map) {
              stateRef.current[keyLower] = new Map(newValue) as any;
            } else if (Array.isArray(newValue)) {
              stateRef.current[keyLower] = [...newValue] as any;
            } else if (typeof newValue === "object" && newValue !== null) {
              stateRef.current[keyLower] = { ...(newValue as object) } as any;
            } else {
              stateRef.current[keyLower] = newValue as any;
            }
          }
        } else {
          // Direct value update
          dispatch({ type: `SET_${key.toUpperCase()}`, payload: value });

          if (stateRef && stateRef.current) {
            if (value instanceof Map) {
              stateRef.current[keyLower] = new Map(value) as any;
            } else if (Array.isArray(value)) {
              stateRef.current[keyLower] = [...value] as any;
            } else if (typeof value === "object" && value !== null) {
              stateRef.current[keyLower] = { ...(value as object) } as any;
            } else {
              stateRef.current[keyLower] = value as any;
            }
          }
        }
      };

      return acc;
    }, {} as BackendStateSystem.StateSetter);
  }, [dispatch, state]);

  const socket = useRef<WebSocketWrapper | undefined>(undefined);
  let wasConnected: boolean = false;

  useEffect(() => {
    const ws = new WebSocketWrapper(`ws://${window.location.hostname}:8765`, {
      onOpen: () => {
        wasConnected = true;
        // Use setter so reducer + ref are in sync
        setters.setConnection({
          ...stateRef.current.connection,
          backend: true,
        });
        toast.success("Connected to backend", {
          duration: 2000,
          id: "backend-connect",
          style: {
            color: teamColor,
            border: "none",
          },
        });
      },
      onClose: () => {
        setters.setConnection({
          ...stateRef.current.connection,
          backend: false,
        });
        if (wasConnected) {
          setters.setConnection({
            backend: false,
            networktables: false,
          });
          toast.warning("Disconnected from backend", {
            duration: 2000,
            id: "backend-disconnect",
            style: {
              color: "yellow",
              border: "none",
            },
          });
          wasConnected = false;
        }
      },
      onMessage: (message: ArrayBufferLike) => {
        const uint8Array = new Uint8Array(message);
        const messageObj = MessageProto.decode(uint8Array);
        switch (messageObj.type) {
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_NETWORK_SETTINGS: {
            const networkSettings = messageObj.setNetworkSettings!;
            setters.setNetworksettings(networkSettings);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_DEVICE_CONNECTION_STATUS: {
            assert(messageObj.setConnectionInfo !== undefined);
            const connectionInfo = messageObj.setConnectionInfo;

            setters.setConnection({
              backend: socket.current?.isConnected() ?? false,
              networktables: connectionInfo.connectedToNetworktables,
            });

            // stateRef mirrored by setter above, no direct assignment needed

            if (!connectionInfo.connectedToNetworktables) {
              toast.warning("Disconnected from NetworkTables", {
                duration: 2000,
                id: "networktables",
                style: {
                  color: "yellow",
                  border: "none",
                },
              });
            } else {
              toast.success("Connected to NetworkTables", {
                duration: 2000,
                id: "networktables",
                style: {
                  color: teamColor,
                  border: "none",
                },
              });
            }

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_ALERT: {
            assert(messageObj.alert !== undefined);

            const alert = messageObj.alert!;
            assert(
              alert.type !== AlertTypeProto.ALERT_TYPE_PROTO_UNSPECIFIED &&
                alert.type !== AlertTypeProto.UNRECOGNIZED,
            );

            let func: typeof toast.info = toast.info;
            let textColor = teamColor;

            typeSwitch: switch (alert.type) {
              case AlertTypeProto.ALERT_TYPE_PROTO_ERROR:
                func = toast.error;
                textColor = "red";
                break typeSwitch;
              case AlertTypeProto.ALERT_TYPE_PROTO_WARNING:
                func = toast.warning;
                textColor = "yellow";
                break typeSwitch;
            }

            func(
              <p className={`whitespace-pre-line`} style={{ color: textColor }}>
                {alert.message.replace(
                  /\[(\/?)(red|yellow|green|bold|italic)\]/g,
                  "",
                )}
              </p>,
              {
                duration: 2000,
                style: {
                  border: "none",
                  color: textColor,
                },
              },
            );

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_DEVICE_INFO: {
            const deviceInfo: DeviceInfoProto = messageObj.deviceInfo!;
            setters.setDeviceinfo(deviceInfo);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_METRICS: {
            const hardwareMetrics: HardwareMetricsProto =
              messageObj.hardwareMetrics!;
            setters.setHardwaremetrics({
              ...stateRef.current.hardwaremetrics,
              ...hardwareMetrics,
              lastFetched: formatHHMMSSLocal(new Date()),
            });

            if (hardwareMetrics.cpuTemp > 90) {
              toast.warning(
                `CPU Temperature Critical: ${hardwareMetrics.cpuTemp}°C`,
                {
                  duration: 2000,
                  style: {
                    color: "yellow",
                    border: "none",
                  },
                },
              );
            }

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE: {
            const pipeline: PipelineProto = messageObj.pipelineInfo!;
            const pipelinesMap = new Map(stateRef.current.pipelines);

            if (!pipelinesMap.has(pipeline.cameraid)) {
              pipelinesMap.set(pipeline.cameraid, new Map());
            }

            pipelinesMap.get(pipeline.cameraid)!.set(pipeline.index, pipeline);
            setters.setPipelines(pipelinesMap);

            const results = new Map(stateRef.current.pipelineresults);
            results.set(pipeline.index, new Map());
            setters.setPipelineresults(results);

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_PIPELINE_TYPES: {
            const types: PipelineTypeProto[] = messageObj.pipelineTypeInfo;
            const newMap = new Map(types.map((type) => [type.type, type]));
            setters.setPipelinetypes(newMap);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_CAMERA: {
            const camera: CameraProto = messageObj.cameraInfo!;
            const newCamerasList = new Map(stateRef.current.cameras);
            newCamerasList.set(camera.index, camera);
            setters.setCameras(newCamerasList);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_INDEX: {
            const msg = messageObj.setPipelineIndex!;
            const camera = stateRef.current.cameras.get(msg.cameraIndex);

            if (camera) {
              camera.pipelineIndex = msg.pipelineIndex;
              const newCamerasList = new Map(stateRef.current.cameras);
              newCamerasList.set(camera.index, camera);
              setters.setCameras(newCamerasList);
            }
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_NAME: {
            const setPipelineNameMSG: SetPipelineNameMessageProto =
              messageObj.setPipelineName!;

            if (!stateRef.current.pipelines.has(setPipelineNameMSG.cameraid)) {
              stateRef.current.pipelines.set(
                setPipelineNameMSG.cameraid,
                new Map(),
              );
            }

            const pipeline = stateRef.current.pipelines
              .get(setPipelineNameMSG.cameraid)!
              .get(setPipelineNameMSG.pipelineIndex);

            if (pipeline) {
              pipeline.name = setPipelineNameMSG.name;
              const newPipelines = new Map(stateRef.current.pipelines);
              newPipelines
                .get(setPipelineNameMSG.cameraid)!
                .set(setPipelineNameMSG.pipelineIndex, pipeline);

              // Use setter so reducer + ref are kept in sync
              setters.setPipelines(newPipelines);
            }
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_LOG: {
            const logMsg: LogMessageProto = messageObj.log!;
            const logs = [...stateRef.current.logs];

            const exists = logs.some(
              (log) => log.timestamp === logMsg.timestamp,
            );

            if (!exists) {
              logs.push(logMsg);
              logs.sort((a, b) => a.timestamp - b.timestamp);
              setters.setLogs(logs);
            }
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_REPORT_CAMERA_PERFORMANCE: {
            const report = messageObj.cameraPerformance!;
            const reports = new Map(stateRef.current.cameraperformance);
            reports.set(report.cameraIndex, report);

            setters.setCameraperformance(reports);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_CALIBRATING: {
            setters.setCalibrating(true);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_CALIBRATION_DATA: {
            const calibData = messageObj.calibrationData!;
            const calibrationMap = new Map(stateRef.current.calibrationdata);

            if (calibrationMap.has(calibData.cameraIndex)) {
              calibrationMap
                .get(calibData.cameraIndex)!
                .set(calibData.resolution, calibData);
            } else {
              calibrationMap.set(
                calibData.cameraIndex,
                new Map([[calibData.resolution, calibData]]),
              );
            }

            setters.setCalibrationdata(calibrationMap);
            setters.setCalibrating(false);

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_SETTING: {
            assert(messageObj.setPipelineSetting !== undefined);
            const setSettingMsg = messageObj.setPipelineSetting!;
            const newPipelines = new Map(stateRef.current.pipelines);

            if (!newPipelines.has(setSettingMsg.cameraid)) {
              newPipelines.set(setSettingMsg.cameraid, new Map());
            }

            const pipeline = newPipelines
              .get(setSettingMsg.cameraid)!
              .get(setSettingMsg.pipelineIndex);

            if (pipeline && setSettingMsg.value) {
              pipeline.settingsValues[setSettingMsg.setting] =
                setSettingMsg.value;
              newPipelines
                .get(setSettingMsg.cameraid)!
                .set(pipeline?.index, pipeline);
              // Use setter to keep reducer + ref in sync
              setters.setPipelines(newPipelines);
            }

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_CAMERA_RECORDING_STATUS: {
            assert(messageObj.setCameraRecordingStatus !== undefined);
            const setstatusmsg = messageObj.setCameraRecordingStatus;
            const statusMap = new Map(stateRef.current.recordingstatuses);
            statusMap.set(setstatusmsg.cameraIndex, setstatusmsg.record);

            setters.setRecordingstatuses(statusMap);

            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_PIPELINE_RESULT: {
            assert(messageObj.pipelineResult !== undefined);
            const pipelineResult = messageObj.pipelineResult;

            const results = new Map(stateRef.current.pipelineresults);

            if (!results.has(pipelineResult.cameraid)) {
              results.set(pipelineResult.cameraid, new Map());
            }

            if (
              !results
                .get(pipelineResult.cameraid)!
                .has(pipelineResult.pipelineIndex)
            ) {
              results
                .get(pipelineResult.cameraid)!
                .set(pipelineResult.pipelineIndex, new Map());
            }

            results
              .get(pipelineResult.cameraid)!
              .get(pipelineResult.pipelineIndex)!
              .set(pipelineResult.key, pipelineResult);

            setters.setPipelineresults(results);

            break;
          }
          default:
            throw new Error(`Unsupported Message Type: ${messageObj.type}`);
        }
      },
    });

    socket.current = ws;
    ws.connect();
    setters.setSocket?.(ws);

    return () => {
      socket.current?.close(); // Close connection on unmount
    };
  }, []);

  return (
    <BackendContextContext.Provider
      value={{
        ...state,
        ...setters,
        socket: socket.current,
        stateRef: stateRef,
      }}
    >
      {children}
    </BackendContextContext.Provider>
  );
};

export const useBackendContext = (): BackendStateSystem.BackendContextType => {
  const context = useContext(BackendContextContext);
  if (!context) {
    throw new Error(
      "useBackendContext must be used within a BackendContextProvider",
    );
  }
  return context;
};
