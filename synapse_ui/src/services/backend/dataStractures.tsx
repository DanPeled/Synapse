import {
  DeviceInfoProto,
  HardwareMetricsProto,
  SetNetworkSettingsProto,
} from "@/generated/messages/v1/device";
import { WebSocketWrapper } from "../websocket";
import { RefObject } from "react";
import {
  CalibrationDataProto,
  CameraPerformanceProto,
  CameraProto,
} from "@/generated/messages/v1/camera";
import {
  PipelineProto,
  PipelineResultProto,
  PipelineTypeProto,
} from "@/generated/messages/v1/pipeline";
import { LogMessageProto } from "@/generated/messages/v1/log";

export type CameraID = number;
export type PipelineID = number;
export type PipelineTypename = string;
export type PipelineResultMap = Map<string, PipelineResultProto>;

export namespace BackendStateSystem {
  export interface State {
    [key: string]: any;
    deviceinfo: DeviceInfoProto;
    hardwaremetrics: HardwareMetricsProto;
    connection: ConnectionState;
    logs: LogMessageProto[];
    socket?: WebSocketWrapper;
    stateRef?: RefObject<State>;
    cameras: Map<CameraID, CameraProto>;
    cameraperformance: Map<CameraID, CameraPerformanceProto>;
    pipelines: Map<CameraID, Map<PipelineID, PipelineProto>>;
    pipelineresults: Map<CameraID, Map<PipelineID, PipelineResultMap>>;
    pipelinetypes: Map<PipelineTypename, PipelineTypeProto>;
    calibrationdata: Map<CameraID, Map<string, CalibrationDataProto>>;
    recordingstatuses: Map<CameraID, boolean>;
    calibrating: boolean;
    networksettings: SetNetworkSettingsProto;
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
