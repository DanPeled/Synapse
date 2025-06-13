export namespace BackendStateSystem {
  export interface State {
    deviceIP: string;
    pipelines: any[];
    hostname: string;
    connection: ConnectionState;
  }

  // Define action types with a discriminated union
  export type StateAction =
    | { type: `SET_${Uppercase<keyof State & string>}`; payload: any }
    | { type: string; payload?: any }; // fallback for unknown actions


  // Type for the setters dynamically created
  export type StateSetter = {
    [K in keyof State as `set${Capitalize<string & K>}`]: (value: State[K]) => void;
  };

  // Context value type combines state and setters
  export type BackendContextType = State & StateSetter;
}

export interface ConnectionState {
  backend: boolean;
  networktables: boolean;
} 
