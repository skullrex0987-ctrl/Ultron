// ULTRON frontend bridge: talks to the laptop Python core over WebSocket.
// Falls back to a no-op if the core isn't running (orb still works).
"use client";

export interface UltronMsg {
  type: string;
  [k: string]: unknown;
}

type Handler = (m: UltronMsg) => void;

export class UltronBridge {
  private ws: WebSocket | null = null;
  private handlers: Handler[] = [];
  private url: string;

  constructor(url = "ws://127.0.0.1:8766") {
    this.url = url;
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);
      this.ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data) as UltronMsg;
          this.handlers.forEach((h) => h(m));
        } catch {
          /* ignore */
        }
      };
      this.ws.onerror = () => {
        // core offline; orb still runs standalone
      };
    } catch {
      /* ignore */
    }
  }

  on(h: Handler) {
    this.handlers.push(h);
  }

  send(m: UltronMsg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(m));
    }
  }
}
