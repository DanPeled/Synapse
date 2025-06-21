import React from "react";
import { render, screen } from "@testing-library/react";
import { BackendContextProvider, useBackendContext } from "@/services/backend/backendContext";

// Mock WebSocketWrapper class
jest.mock("@/services/websocket", () => ({
  __esModule: true,
  default: class WebSocketWrapper {
    connect() { }
  },
  Message: {},
}));

const ContextConsumer = () => {
  const context = useBackendContext();
  return (
    <>
      <div data-testid="hostname">{context.deviceinfo.hostname ?? "null"}</div>
      <div data-testid="cpu-temp">{context.hardwaremetrics.cpu_temp}</div>
    </>
  );
};

describe("BackendContextProvider", () => {
  it("provides default context values", () => {
    render(
      <BackendContextProvider>
        <ContextConsumer />
      </BackendContextProvider>
    );

    expect(screen.getByTestId("hostname").textContent).toBe("null");
    expect(screen.getByTestId("cpu-temp").textContent).toBe("0");
  });

  it("updates context with setter", () => {
    const TestComponent = () => {
      const context = useBackendContext();

      React.useEffect(() => {
        context.setDeviceinfo?.({
          hostname: "updated-host",
          ip: "192.168.1.1",
          platform: "Linux",
          networkInterfaces: ["eth0"],
        });
      }, []);

      return <div data-testid="hostname">{context.deviceinfo.hostname}</div>;
    };

    render(
      <BackendContextProvider>
        <TestComponent />
      </BackendContextProvider>
    );

    expect(screen.getByTestId("hostname").textContent).toBe("updated-host");
  });
});
