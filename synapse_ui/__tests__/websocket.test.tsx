/**
 * @jest-environment jsdom
 */

import WebSocketWrapper, { createMessage, Message } from "@/services/websocket";

const MockWebSocket = jest.fn().mockImplementation(() => {
  return {
    readyState: WebSocket.CONNECTING,
    onopen: null,
    onclose: null,
    onmessage: null,
    onerror: null,
    send: jest.fn(),
    close: jest.fn(),
  };
});

describe("WebSocketWrapper", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    (global as any).WebSocket = MockWebSocket;
    MockWebSocket.mockClear();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllTimers();
  });

  test("calls onOpen when websocket opens", () => {
    const onOpen = jest.fn();
    const wsInstance = new WebSocketWrapper("ws://test", { onOpen });
    wsInstance.connect();

    const ws = (wsInstance as any).ws;
    ws.readyState = WebSocket.OPEN;
    ws.onopen?.(new Event("open"));

    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  test("calls onClose and attempts reconnect after close if not forcedClose", () => {
    const onClose = jest.fn();
    const wsInstance = new WebSocketWrapper("ws://test", { onClose, reconnectInterval: 100 });
    wsInstance.connect();

    const ws = (wsInstance as any).ws;
    ws.onclose?.(new CloseEvent("close"));

    expect(onClose).toHaveBeenCalledTimes(1);

    // reconnect after 100ms
    jest.advanceTimersByTime(99);
    expect(MockWebSocket).toHaveBeenCalledTimes(1);

    jest.advanceTimersByTime(1);
    expect(MockWebSocket).toHaveBeenCalledTimes(2);
  });

  test("does NOT reconnect after close if forcedClose is true", () => {
    const onClose = jest.fn();
    const wsInstance = new WebSocketWrapper("ws://test", { onClose, reconnectInterval: 100 });
    wsInstance.connect();

    wsInstance.close();

    const ws = (wsInstance as any).ws;
    ws.onclose?.(new CloseEvent("close"));

    expect(onClose).toHaveBeenCalledTimes(1);

    jest.advanceTimersByTime(100);
    // No reconnect, only 1 instance created
    expect(MockWebSocket).toHaveBeenCalledTimes(1);
  });

  test("calls onMessage with the message data", () => {
    const onMessage = jest.fn();
    const wsInstance = new WebSocketWrapper("ws://test", { onMessage });
    wsInstance.connect();

    const ws = (wsInstance as any).ws;
    ws.onmessage?.(new MessageEvent("message", { data: "hello" }));

    expect(onMessage).toHaveBeenCalledWith("hello");
  });

  test("calls onError on websocket error", () => {
    const onError = jest.fn();
    const wsInstance = new WebSocketWrapper("ws://test", { onError });
    wsInstance.connect();

    const ws = (wsInstance as any).ws;
    ws.onerror?.(new Event("error"));

    expect(onError).toHaveBeenCalledTimes(1);
  });

  test("send calls WebSocket.send if connected", () => {
    const wsInstance = new WebSocketWrapper("ws://test");
    wsInstance.connect();

    const ws = (wsInstance as any).ws;
    ws.readyState = WebSocket.OPEN;

    wsInstance.send("test message");

    expect(ws.send).toHaveBeenCalledWith("test message");
  });

  test("close sets forcedClose and calls websocket.close", () => {
    const wsInstance = new WebSocketWrapper("ws://test");
    wsInstance.connect();

    wsInstance.close();

    expect((wsInstance as any).forcedClose).toBe(true);

    const ws = (wsInstance as any).ws;
    expect(ws.close).toHaveBeenCalled();
  });

  test("isConnected returns true only when websocket is open", () => {
    const wsInstance = new WebSocketWrapper("ws://test");
    wsInstance.connect();

    const ws = (wsInstance as any).ws;

    ws.readyState = WebSocket.OPEN;
    expect(wsInstance.isConnected()).toBe(true);

    ws.readyState = WebSocket.CLOSED;
    expect(wsInstance.isConnected()).toBe(true);

    (wsInstance as any).ws = null;
    expect(wsInstance.isConnected()).toBe(false);
  });
});

describe("createMessage", () => {
  test("creates correct JSON string", () => {
    const json = createMessage("type1", { foo: "bar" });
    expect(json).toBe(JSON.stringify({ type: "type1", message: { foo: "bar" } }));
  });
});

describe("Message class", () => {
  test("assigns properties", () => {
    const msg = new Message("hello", 123);
    expect(msg.type).toBe("hello");
    expect(msg.message).toBe(123);
  });
});
