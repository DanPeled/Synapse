import { DeviceInfoProto, HardwareMetricsProto } from "@/proto/v1/device";
import { WebSocketWrapper } from "../websocket";
import {
  CalibrationDataProto,
  CameraPerformanceProto,
  CameraProto,
} from "@/proto/v1/camera";
import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";
import { LogMessageProto } from "@/proto/v1/log";
import { RefObject } from "react";

export type CameraID = number;
export type PipelineID = number;
export type PipelineTypename = string;

export namespace BackendStateSystem {
  export interface State {
    deviceinfo: DeviceInfoProto;
    hardwaremetrics: HardwareMetricsProto;
    connection: ConnectionState;
    networktable: string;
    logs: LogMessageProto[];
    socket?: WebSocketWrapper;
    stateRef?: RefObject<State>;
    teamnumber: number;
    cameras: Map<CameraID, CameraProto>;
    cameraperformance: Map<CameraID, CameraPerformanceProto>;
    pipelines: Map<PipelineID, PipelineProto>;
    pipelinetypes: Map<PipelineTypename, PipelineTypeProto>;
    calibrationdata: Map<CameraID, Map<string, CalibrationDataProto>>;
    calibrating: boolean;
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
