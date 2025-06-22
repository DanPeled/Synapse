type WebSocketWrapperOptions = {
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onMessage?: (message: ArrayBufferLike) => void;
  onError?: (event: Event) => void;
  reconnectInterval?: number;
};

export class WebSocketWrapper {
  private url: string;
  private ws: WebSocket | null = null;
  private forcedClose = false;
  private reconnectInterval: number;

  private onOpen: (event: Event) => void;
  private onClose: (event: CloseEvent) => void;
  private onMessage: (message: ArrayBufferLike) => void;
  private onError: (event: Event) => void;

  constructor(url: string, options: WebSocketWrapperOptions = {}) {
    this.url = url;
    this.onOpen = options.onOpen || (() => {});
    this.onClose = options.onClose || (() => {});
    this.onMessage = options.onMessage || (() => {});
    this.onError = options.onError || (() => {});
    this.reconnectInterval = options.reconnectInterval ?? 200;
  }

  public connect() {
    this.ws = new WebSocket(this.url);
    this.ws.binaryType = "arraybuffer"; // <--- Important!

    this.ws.onopen = (event: Event) => {
      this.onOpen(event);
    };

    this.ws.onclose = (event: CloseEvent) => {
      this.onClose(event);
      if (!this.forcedClose) {
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    };

    this.ws.onmessage = (event: MessageEvent) => {
      if (
        event.data instanceof ArrayBuffer ||
        event.data instanceof SharedArrayBuffer
      ) {
        this.onMessage(event.data);
      } else if (typeof event.data === "string") {
        this.onMessage(new TextEncoder().encode(event.data).buffer);
      } else {
        console.warn("Unsupported message type", event.data);
      }
    };

    this.ws.onerror = (event: Event) => {
      this.onError(event);
    };
  }

  // Send binary data (protobuf serialized bytes)
  public sendBinary(data: Uint8Array | ArrayBuffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      console.warn("WebSocket is not open. Cannot send binary message.");
    }
  }

  // Optional: keep string send for JSON or other text
  public send(data: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      console.warn("WebSocket is not open. Cannot send message.");
    }
  }

  public close() {
    this.forcedClose = true;
    if (this.ws) {
      this.ws.close();
    }
  }

  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
