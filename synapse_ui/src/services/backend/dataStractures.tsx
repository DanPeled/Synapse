import { DeviceInfoProto, HardwareMetricsProto } from "@/proto/v1/device";
import { PipelineManagement } from "./pipelineContext";
import { WebSocketWrapper } from "../websocket";

export namespace BackendStateSystem {
  export interface State {
    deviceinfo: DeviceInfoProto;
    hardwaremetrics: HardwareMetricsProto;
    connection: ConnectionState;
    networktable: string;
    pipelinecontext: PipelineManagement.PipelineContext;
    logs: Log[];
    socket?: WebSocketWrapper | null;
    networktablesserver: string | null;
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
      value: State[K] | ((prev: State[K]) => State[K])
    ) => void;
  };

  // Context value type combines state and setters
  export type BackendContextType = State & StateSetter;
}

export interface ConnectionState {
  backend: boolean;
  networktables: boolean;
}
