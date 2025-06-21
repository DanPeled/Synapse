import WebSocketWrapper from "../websocket";
import { PipelineManagement } from "./pipelineContext";

export namespace BackendStateSystem {
  export interface Pipeline {
    name: string;
    type: string;
    index: number;
  }

  export interface State {
    deviceinfo: DeviceInfo;
    hardwaremetrics: HardwareMetrics;
    pipelines: Pipeline[];
    connection: ConnectionState;
    networktable: string;
    pipelineContext: PipelineManagement.PipelineContext;
    logs: Log[];
    socket?: WebSocketWrapper | null;
    networkTablesServer: string | null;
  }

  export interface Log {
    type: "warning" | "info" | "error";
    message: string;
  }

  // Define action types with a discriminated union
  export type StateAction =
    | { type: `SET_${Uppercase<keyof State & string>}`; payload: unknown }
    | { type: string; payload?: unknown }; // fallback for unknown actions

  // Type for the setters dynamically created
  export type StateSetter = {
    [K in keyof State as `set${Capitalize<string & K>}`]: (
      value: State[K],
    ) => void;
  };

  // Context value type combines state and setters
  export type BackendContextType = State & StateSetter;
}

export interface ConnectionState {
  backend: boolean;
  networktables: boolean;
}

export interface DeviceInfo {
  hostname: string | null;
  ip: string | null;
  platform: string;
  networkInterfaces: string[];
}

export interface HardwareMetrics {
  cpu_temp: number;
  cpu_usage: number;
  disk_usage: number;
  ram_usage: number;
  uptime: number;
  last_fetched: string;
}
