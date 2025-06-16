import React, {
  createContext,
  useContext,
  useReducer,
  ReactNode,
  useState,
  useEffect,
} from "react";
import WebSocketWrapper, { Message } from "../websocket";
import { BackendStateSystem, DeviceInfo, HardwareMetrics } from "./dataStractures";
import { PipelineManagement } from "./pipelineContext";

const initialState: BackendStateSystem.State = {
  deviceinfo: {
    hostname: "Unknown",
    ip: "127.0.0.1",
    platform: "Unknown",
    networkInterfaces: ["eth0"]
  },
  hardwaremetrics: {
    cpu_temp: 0,
    cpu_usage: 0,
    disk_usage: 0,
    ram_usage: 0,
    uptime: 0
  },
  pipelines: [],
  connection: {
    backend: false,
    networktables: false,
  },
  networktable: "Synapse",
  pipelineContext: new PipelineManagement.PipelineContext([
    new PipelineManagement.Pipeline("Sample Pipeline", "ApriltagPipeline", new Map()),
    new PipelineManagement.Pipeline("Another Pipeline", "ApriltagPipeline", new Map())
  ], [
    "ApriltagPipeline"
  ]),
  logs: []
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

  const [socket] = useState(() => {
    return new WebSocketWrapper("ws://localhost:8765", {
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
        const json = JSON.parse(message);
        const messageObj = new Message(json["type"], json["message"]);

        switch (messageObj.type) {
          case "send_device_info":
            const deviceInfo: DeviceInfo = (messageObj.message as DeviceInfo);
            setters.setDeviceinfo({ ...state.deviceinfo, ip: deviceInfo.ip, platform: deviceInfo.platform, hostname: deviceInfo.hostname ?? "Unknown", networkInterfaces: deviceInfo.networkInterfaces });
            break;
          case "hardware_metrics":
            const hardwareMetrics: HardwareMetrics = (messageObj.message as HardwareMetrics);
            setters.setHardwaremetrics({
              ...state.hardwaremetrics,
              cpu_temp: hardwareMetrics.cpu_temp,
              cpu_usage: hardwareMetrics.cpu_usage,
              disk_usage: hardwareMetrics.disk_usage,
              ram_usage: hardwareMetrics.ram_usage,
              uptime: hardwareMetrics.uptime,
            });
            break;
        }
      },
    });
  });

  useEffect(() => {
    socket.connect();
  }, [socket]);

  return (
    <BackendContextContext.Provider value={{ ...state, ...setters }}>
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
