export default class WebSocketWrapper {
  /**
   * @param {string} url - WebSocket server URL
   * @param {object} options - Optional config callbacks and settings
   * options = {
   *   onOpen: () => {},              // called on open
   *   onClose: (event) => {},       // called on close
   *   onMessage: (message) => {},   // called on message
   *   onError: (error) => {},       // called on error
   *   reconnectInterval: number,    // ms to wait before reconnect (default 2000)
   * }
   */
  constructor(url, options = {}) {
    this.url = url;
    this.onOpen = options.onOpen || (() => {});
    this.onClose = options.onClose || (() => {});
    this.onMessage = options.onMessage || (() => {});
    this.onError = options.onError || (() => {});
    this.reconnectInterval = options.reconnectInterval || 200;

    this.ws = null;
    this.forcedClose = false; // prevent reconnect when manually closed
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = (event) => {
      this.onOpen(event);
    };

    this.ws.onclose = (event) => {
      this.onClose(event);
      if (!this.forcedClose) {
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    };

    this.ws.onmessage = (event) => {
      this.onMessage(event.data);
    };

    this.ws.onerror = (event) => {
      this.onError(event);
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      console.warn("WebSocket is not open. Cannot send message.");
    }
  }

  close() {
    this.forcedClose = true;
    if (this.ws) {
      this.ws.close();
    }
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}
