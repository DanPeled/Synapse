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
import { DeviceInfoProto, HardwareMetricsProto } from "@/proto/v1/device";
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
import { Camera } from "three/src/Three.Core.js";

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
    hostname: "Unknown",
    ip: "127.0.0.1",
    platform: "Unknown",
    networkInterfaces: ["eth0"],
  },
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
  networktable: "Synapse",
  logs: [],
  cameras: new Map(),
  cameraPerformance: new Map(),
  teamnumber: 0,
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
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const setters = React.useMemo(() => {
    return Object.keys(initialState).reduce((acc, key) => {
      const functionName =
        `set${key.charAt(0).toUpperCase()}${key.slice(1)}` as keyof BackendStateSystem.StateSetter;
      acc[functionName] = (value: unknown | ((prev: unknown) => unknown)) => {
        if (typeof value === "function") {
          const keyLower = key.toLowerCase() as keyof BackendStateSystem.State;
          const currentSlice = state[keyLower];
          const newValue = (value as Function)(currentSlice);
          dispatch({ type: `SET_${key.toUpperCase()}`, payload: newValue });
        } else {
          // Direct value update
          dispatch({ type: `SET_${key.toUpperCase()}`, payload: value });
        }
      };
      return acc;
    }, {} as BackendStateSystem.StateSetter);
  }, [dispatch, state]);

  const socket = useRef<WebSocketWrapper | undefined>(undefined);

  useEffect(() => {
    const ws = new WebSocketWrapper(`ws://${window.location.hostname}:8765`, {
      onOpen: () => {
        dispatch({
          type: "SET_CONNECTION",
          payload: { ...stateRef.current.connection, backend: true },
        });
      },
      onClose: () => {
        dispatch({
          type: "SET_CONNECTION",
          payload: { ...stateRef.current.connection, backend: false },
        });
      },
      onMessage: (message: ArrayBufferLike) => {
        const uint8Array = new Uint8Array(message);
        const messageObj = MessageProto.decode(uint8Array);
        // console.log(messageObj);
        switch (messageObj.type) {
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_DEVICE_INFO: {
            const deviceInfo: DeviceInfoProto = messageObj.deviceInfo!;

            stateRef.current.deviceinfo = deviceInfo;
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
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE: {
            const pipeline: PipelineProto = messageObj.pipelineInfo!;
            const pipelines = stateRef.current.pipelines;
            pipelines.set(pipeline.index, pipeline);
            setters.setPipelines(pipelines);
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

            const pipeline = stateRef.current.pipelines.get(
              setPipelineNameMSG.pipelineIndex,
            );

            if (pipeline) {
              pipeline.name = setPipelineNameMSG.name;
              const newPipelines = new Map(stateRef.current.pipelines);
              newPipelines.set(setPipelineNameMSG.pipelineIndex, pipeline);
              setters.setPipelines(newPipelines);
            }
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_LOG: {
            const logMsg: LogMessageProto = messageObj.log!;
            const logs = [...stateRef.current.logs];
            stateRef.current.logs = logs; // Keep the ref updated!

            const exists = logs.some(
              (log) => log.timestamp === logMsg.timestamp,
            );

            if (!exists) {
              logs.push(logMsg);
              // Sort logs by timestamp ascending (older first)
              logs.sort((a, b) => a.timestamp - b.timestamp);
              setters.setLogs(logs);
            }
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_REPORT_CAMERA_PERFORMANCE: {
            const report = messageObj.cameraPerformance!;
            const reports = new Map(stateRef.current.cameraPerformance);
            reports.set(report.cameraIndex, report);

            setters.setCameraPerformance(reports);
            stateRef.current.cameraPerformance = reports;
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SET_SETTING: {
            // TODO: handle change from external source (NT)
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
      value={{ ...state, ...setters, socket: socket.current }}
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
