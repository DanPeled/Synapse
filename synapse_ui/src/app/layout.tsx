"use client"; // make sure this component is client-side

import "./globals.css";
import { useEffect, useState } from "react";
import {
  BackendContextProvider,
  useBackendContext,
} from "@/services/backend/backendContext";
import { teamColor, toastColor } from "@/services/style";
import { Sidebar } from "@/widgets/sidebar";
import { Toaster } from "sonner";
import { ProgramLogsDialog } from "./settings/programLogsDialog";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-mono">
        <BackendContextProvider>
          <App>{children}</App>
        </BackendContextProvider>
      </body>
    </html>
  );
}

function App({ children }: { children: React.ReactNode }) {
  const [isLogsWindowOpen, setIsLogsWindowOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        (e.target as HTMLElement).isContentEditable
      ) {
        return; // ignore typing
      }

      if (e.code === "Backquote" || e.key === "~") {
        e.preventDefault();
        setIsLogsWindowOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const { logs } = useBackendContext();
  return (
    <div className="flex min-h-screen" style={{ backgroundColor: "#8a1e60" }}>
      {" "}
      <Sidebar compact={true} />
      <div className="flex-1" style={{ marginLeft: "3.75rem" }}>
        {children}
        {isLogsWindowOpen && (
          <ProgramLogsDialog
            onClose={() => setIsLogsWindowOpen(false)}
            visible={isLogsWindowOpen}
            setVisible={setIsLogsWindowOpen}
            logs={logs}
          />
        )}
        <Toaster
          position="bottom-right"
          richColors
          toastOptions={{
            style: {
              fontSize: "1.2rem",
              backgroundColor: toastColor,
              color: teamColor,
              border: "none",
            },
          }}
        />
      </div>
    </div>
  );
}
