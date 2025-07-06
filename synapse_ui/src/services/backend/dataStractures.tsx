import { DeviceInfoProto, HardwareMetricsProto } from "@/proto/v1/device";
import { WebSocketWrapper } from "../websocket";
import { CameraProto } from "@/proto/v1/camera";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";

export namespace BackendStateSystem {
  export interface State {
    deviceinfo: DeviceInfoProto;
    hardwaremetrics: HardwareMetricsProto;
    connection: ConnectionState;
    networktable: string;
    logs: Log[];
    socket?: WebSocketWrapper;
    networktablesserver: string | null;
    cameras: CameraProto[];
    pipelines: Map<number, PipelineProto>;
    pipelinetypes: Map<string, PipelineTypeProto>;
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
      value: State[K] | ((prev: State[K]) => State[K]),
    ) => void;
  };

  // Context value type combines state and setters
  export type BackendContextType = State & StateSetter;
}

export interface ConnectionState {
  backend: boolean;
  networktables: boolean;
}
