import React, { createContext, useContext, useReducer, ReactNode, useState, useEffect } from 'react';
import WebSocketWrapper from '../websocket';
import { BackendStateSystem } from './dataStractures';

const initialState: BackendStateSystem.State = {
  deviceIP: "127.0.0.1",
  pipelines: [],
  hostname: "Sample Hostname",
  connection: {
    backend: false,
    networktables: false,
  }
};

export const BackendStateKeys = Object.keys(initialState).reduce((acc, key) => {
  acc[key] = key;
  return acc;
}, {} as { [key: string]: string });

// Reducer function with typed state and action
function reducer(state: BackendStateSystem.State, action: BackendStateSystem.StateAction): BackendStateSystem.State {
  if (action.type.startsWith('SET_')) {
    const key = action.type.slice(4).toLowerCase() as keyof BackendStateSystem.State;
    if (key in state) {
      return { ...state, [key]: action.payload };
    }
  }
  return state;
}

// Create the context with a default undefined value
const BackendContextContext = createContext<BackendStateSystem.BackendContextType | undefined>(undefined);

// Props type for the provider
interface BackendContextProviderProps {
  children: ReactNode;
  onChange?: (key: keyof BackendStateSystem.State, value: BackendStateSystem.State[keyof BackendStateSystem.State]) => void;
}

function handleValueChange(key: string, value: any) {
  switch (key) {
    case BackendStateKeys.deviceIP:
      break;
  }
}

export const BackendContextProvider: React.FC<BackendContextProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [socket, setSocket] = useState(() =>
    new WebSocketWrapper("ws://localhost:8765", {
      onOpen: () => {
        dispatch({
          type: 'SET_CONNECTION',
          payload: { ...state.connection, backend: true }
        });
      },
      onClose: () => {
        dispatch({
          type: 'SET_CONNECTION',
          payload: { ...state.connection, backend: false }
        });
      },
      onMessage: (message) => {
        console.log(message);
      }
    },
    ),
  );

  useEffect(() => {
    socket.connect();
  }, [socket]);

  const setters = Object.keys(initialState).reduce((acc, key) => {
    const functionName = `set${key.charAt(0).toUpperCase()}${key.slice(1)}` as keyof BackendStateSystem.StateSetter;
    acc[functionName] = (value: any) => {
      dispatch({ type: `SET_${key.toUpperCase()}`, payload: value });
      if (handleValueChange) {
        handleValueChange(key as keyof BackendStateSystem.State, value);
      }
    };
    return acc;
  }, {} as BackendStateSystem.StateSetter);


  return (
    <BackendContextContext.Provider value={{ ...state, ...setters }}>
      {children}
    </BackendContextContext.Provider>
  );
};

export const useBackendContext = (): BackendStateSystem.BackendContextType => {
  const context = useContext(BackendContextContext);
  if (!context) {
    throw new Error('useBackendContext must be used within a BackendContextProvider');
  }
  return context;
};
