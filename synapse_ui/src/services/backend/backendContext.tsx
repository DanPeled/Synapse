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
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { CameraProto } from "@/proto/v1/camera";
import { SettingValueProto } from "@/proto/settings/v1/value";

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
  logs: [] as BackendStateSystem.Log[],
  cameras: [],
  networktablesserver: null,
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
          payload: { ...state.connection, backend: true },
        });
      },
      onClose: () => {
        dispatch({
          type: "SET_CONNECTION",
          payload: { ...state.connection, backend: false },
        });
      },
      onMessage: (message: ArrayBufferLike) => {
        const uint8Array = new Uint8Array(message);
        const messageObj = MessageProto.decode(uint8Array);
        // console.log(messageObj);
        switch (messageObj.type) {
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_DEVICE_INFO:
            const deviceInfo: DeviceInfoProto = messageObj.deviceInfo!;
            setters.setDeviceinfo({
              ...state.deviceinfo,
              ...deviceInfo,
            });

            break;
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_METRICS:
            const hardwareMetrics: HardwareMetricsProto =
              messageObj.hardwareMetrics!;
            setters.setHardwaremetrics({
              ...state.hardwaremetrics,
              ...hardwareMetrics,
              lastFetched: formatHHMMSSLocal(new Date()),
            });
            break;
          case MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_PIPELINE:
            const pipeline: PipelineProto = messageObj.pipelineInfo!;
            const pipelines = state.pipelines;
            pipelines.set(pipeline.index, pipeline);
            setters.setPipelines(pipelines);
            break;
          case MessageTypeProto.MESSAGE_TYPE_PROTO_SEND_PIPELINE_TYPES: {
            const types: PipelineTypeProto[] = messageObj.pipelineTypeInfo;
            const newMap = new Map(types.map((type) => [type.type, type]));
            setters.setPipelinetypes(newMap);
            break;
          }
          case MessageTypeProto.MESSAGE_TYPE_PROTO_ADD_CAMERA: {
            const camera: CameraProto = messageObj.cameraInfo!;
            let newCamerasList = [...state.cameras, camera];
            newCamerasList = newCamerasList.sort(
              (a, b) => (a?.index ?? 0) - (b?.index ?? 0),
            );
            setters.setCameras(newCamerasList);
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
