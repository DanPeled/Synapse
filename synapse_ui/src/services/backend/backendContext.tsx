"use client";

import React, {
  createContext,
  useContext,
  useReducer,
  ReactNode,
  useEffect,
  useRef,
} from "react";
import WebSocketWrapper, { Message } from "../websocket";
import {
  BackendStateSystem,
  DeviceInfo,
  HardwareMetrics,
} from "./dataStractures";
import { PipelineManagement } from "./pipelineContext";

const initialState: BackendStateSystem.State = {
  deviceinfo: {
    hostname: null,
    ip: null,
    platform: "Unknown",
    networkInterfaces: ["eth0"],
  },
  hardwaremetrics: {
    cpu_temp: 0,
    cpu_usage: 0,
    disk_usage: 0,
    ram_usage: 0,
    uptime: 0,
    last_fetched: new Date().toLocaleTimeString(),
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

function handleValueChange(key: string, value: any) {
  switch (key) {
    case BackendStateKeys.deviceInfo:
      break;
  }
}

export const BackendContextProvider: React.FC<BackendContextProviderProps> = ({
  children,
}) => {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setters = Object.keys(initialState).reduce((acc, key) => {
    const functionName =
      `set${key.charAt(0).toUpperCase()}${key.slice(1)}` as keyof BackendStateSystem.StateSetter;
    acc[functionName] = (value: any) => {
      dispatch({ type: `SET_${key.toUpperCase()}`, payload: value });
      if (handleValueChange) {
        handleValueChange(key as keyof BackendStateSystem.State, value);
      }
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
      onMessage: (message) => {
        const jsonArr = splitConcatenatedJSON(message);
        jsonArr.forEach((val) => {
          const messageObj = val as Message;
          switch (messageObj.type) {
            case "send_device_info":
              const deviceInfo: DeviceInfo = messageObj.message as DeviceInfo;
              setters.setDeviceinfo({
                ...state.deviceinfo,
                ip: deviceInfo.ip,
                platform: deviceInfo.platform,
                hostname: deviceInfo.hostname ?? "Unknown",
                networkInterfaces: deviceInfo.networkInterfaces,
              });
              break;
            case "hardware_metrics":
              const hardwareMetrics: HardwareMetrics =
                messageObj.message as HardwareMetrics;
              setters.setHardwaremetrics({
                ...state.hardwaremetrics,
                ...hardwareMetrics,
                last_fetched: formatHHMMSSLocal(new Date()),
              });
              break;
            case "log":
              // Handle logs if needed
              break;
          }
        });
      },
    });

    socket.current = ws;
    ws.connect();
    setters.setSocket?.(ws);
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

function splitConcatenatedJSON(input: string): unknown[] {
  const values: unknown[] = [];
  let depth = 0;
  let inString = false;
  let escape = false;
  let start = 0;

  for (let i = 0; i < input.length; i++) {
    const char = input[i];

    if (inString) {
      if (escape) {
        escape = false;
      } else if (char === "\\") {
        escape = true;
      } else if (char === '"') {
        inString = false;
      }
    } else {
      if (char === '"') {
        inString = true;
      } else if (char === "{" || char === "[") {
        depth++;
      } else if (char === "}" || char === "]") {
        depth--;
      }
    }

    if (depth === 0 && !inString && i >= start) {
      const chunk = input.slice(start, i + 1).trim();
      if (chunk) {
        try {
          values.push(JSON.parse(chunk));
        } catch (e) {
          console.error("Failed to parse:", chunk);
        }
      }
      start = i + 1;
    }
  }

  return values;
}

function formatHHMMSSLocal(date: Date): string {
  const pad = (n: number): string => n.toString().padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
