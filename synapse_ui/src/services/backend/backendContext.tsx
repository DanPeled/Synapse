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
import { PipelineManagement } from "./pipelineContext";
import { DeviceInfoProto, HardwareMetricsProto } from "@/proto/v1/device";
import { MessageProto } from "@/proto/v1/message";
import { WebSocketWrapper } from "../websocket";

const initialState: BackendStateSystem.State = {
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
    lastFetched: undefined,
  },
  pipelines: [],
  connection: {
    backend: false,
    networktables: false,
  },
  networktable: "Synapse",
  pipelineContext: new PipelineManagement.PipelineContext(
    [
      new PipelineManagement.Pipeline(
        "Sample Pipeline",
        "ApriltagPipeline",
        new Map(),
      ),
      new PipelineManagement.Pipeline(
        "Another Pipeline",
        "ApriltagPipeline",
        new Map(),
      ),
    ],
    ["ApriltagPipeline"],
  ),
  logs: [] as BackendStateSystem.Log[],
  networkTablesServer: null,
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

  const setters = Object.keys(initialState).reduce((acc, key) => {
    const functionName =
      `set${key.charAt(0).toUpperCase()}${key.slice(1)}` as keyof BackendStateSystem.StateSetter;
    acc[functionName] = (value: unknown) => {
      dispatch({ type: `SET_${key.toUpperCase()}`, payload: value });
    };
    return acc;
  }, {} as BackendStateSystem.StateSetter);

  const socket = useRef<WebSocketWrapper | null>(null);

  useEffect(() => {
    const ws = new WebSocketWrapper("ws://localhost:8765", {
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
        console.log(messageObj);
        if (messageObj.payload !== undefined) {
          switch (messageObj.type) {
            case "send_device_info":
              const deviceInfo: DeviceInfoProto = DeviceInfoProto.decode(
                messageObj.payload.value,
              );
              setters.setDeviceinfo({
                ...state.deviceinfo,
                ...deviceInfo,
              });
              break;
            case "hardware_metrics":
              const hardwareMetrics: HardwareMetricsProto =
                HardwareMetricsProto.decode(messageObj.payload.value);
              console.log(hardwareMetrics);
              console.log(messageObj.payload);
              setters.setHardwaremetrics({
                ...state.hardwaremetrics,
                ...hardwareMetrics,
                lastFetched: formatHHMMSSLocal(new Date()),
              });
              break;
            case "log":
              // Handle logs if needed
              break;
          }
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

function formatHHMMSSLocal(date: Date): string {
  const pad = (n: number): string => n.toString().padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
