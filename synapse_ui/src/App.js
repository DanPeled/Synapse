import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./widgets/Sidebar";
import Dashboard from "./pages/dashboard/Dashboard";
import Settings from "./pages/settings/Settings";
import CameraConfig from "./pages/cameraConfig/CameraConfig";
import { createGlobalStyle } from "styled-components";
import { BackendContextProvider } from "./services/backend/backendContext";
import { darken } from "polished";

const GlobalStyle = createGlobalStyle`
 body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
  }
  ::-webkit-scrollbar {
    width: 12px;
  }
  ::-webkit-scrollbar-track {
    background: #222;
    border-radius: 6px;
  }
  ::-webkit-scrollbar-thumb {
    background-color: #555;
    border-radius: 6px;
    border: 3px solid #222;
  }
  ::-webkit-scrollbar-thumb:hover {
    background-color: #888;
  }

  * {
    scrollbar-width: thin;
    scrollbar-color: #555 #222;
  }
`;

function AppContent() {
  return (
    <div style={{ backgroundColor: darken(0.1, "#8a1e60"), overflowX: "hidden" }}>
      <GlobalStyle />
      <div className="App">
        <Sidebar />
        <main
          style={{
            flex: 1,
            height: "100vh",
            color: "white",
            padding: "5px 10px", // top right bottom left
            marginLeft: "60px"
          }}
        >
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/camera" element={<CameraConfig />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <BackendContextProvider>
      <AppContent />
    </BackendContextProvider>
  );
}

export default App;
