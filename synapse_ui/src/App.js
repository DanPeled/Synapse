import React, { useState, useEffect } from "react";
import Sidebar from "./widgets/Sidebar";
import Dashboard from "./pages/dashboard/Dashboard";
import Settings from "./pages/settings/Settings";
import CameraConfig from "./pages/cameraConfig/CameraConfig";
import { createGlobalStyle } from "styled-components";
import { BackendContextProvider, useBackendContext } from "./services/backend/backendContext";

const GlobalStyle = createGlobalStyle`
  /* Webkit-based browsers (Chrome, Safari, Edge) */
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

  /* Firefox */
  * {
    scrollbar-width: thin;
    scrollbar-color: #555 #222;
  }
`;

function AppContent() {
  const [view, setView] = useState(window.location.hash);

  const onHashChange = () => {
    setView(window.location.hash);
  };

  useEffect(() => {
    if (
      !window.location.hash ||
      window.location.hash === "#/" ||
      window.location.hash === "#"
    ) {
      window.location.hash = "#/dashboard";
    }
  }, []);

  useEffect(() => {
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return (
    <>
      <GlobalStyle />
      <div
        className="App"
        style={{ display: "flex", height: "100vh", overflow: "hidden" }}
      >
        <Sidebar />
        <main
          style={{
            flex: 1,
            height: "100vh",
            padding: 15,
            backgroundColor: "#8a1e60",
            color: "white",
            overflowY: "auto",
            overflowX: "hidden",
          }}
        >
          {view === "#/dashboard" && <Dashboard />}
          {view === "#/settings" && <Settings />}
          {view === "#/camera" && <CameraConfig />}
        </main>
      </div>
    </>
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
