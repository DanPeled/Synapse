type WebSocketWrapperOptions = {
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onMessage?: (message: string) => void;
  onError?: (event: Event) => void;
  reconnectInterval?: number;
};

export default class WebSocketWrapper {
  private url: string;
  private ws: WebSocket | null = null;
  private forcedClose = false;
  private reconnectInterval: number;

  private onOpen: (event: Event) => void;
  private onClose: (event: CloseEvent) => void;
  private onMessage: (message: string) => void;
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
      this.onMessage(event.data);
    };

    this.ws.onerror = (event: Event) => {
      this.onError(event);
    };
  }

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

export class Message {
  constructor(
    public type: string,
    public message: unknown,
  ) {}
}

export function createMessage(type: string, message: unknown): string {
  return JSON.stringify({
    type: type,
    message: message,
  });
}
