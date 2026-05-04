export type WsStatus = 'disconnected' | 'connecting' | 'ready' | 'typing';

type InboundFrame =
  | { type: 'ready'; session_id: string }
  | { type: 'typing' }
  | { type: 'response'; content: string; reasoning: string | null }
  | { type: 'pong' }
  | { type: 'error'; message: string };

export interface WsCallbacks {
  onStatus: (s: WsStatus) => void;
  onMessage: (content: string) => void;
  onError: (msg: string) => void;
  onSessionId: (id: string) => void;
}

export interface WsClient {
  connect: () => void;
  send: (content: string) => void;
  disconnect: () => void;
}

export function createWsClient(token: string, callbacks: WsCallbacks): WsClient {
  let ws: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  function connect() {
    if (destroyed) return;
    callbacks.onStatus('connecting');

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => {
      ws!.send(JSON.stringify({ type: 'auth', token }));
    };

    ws.onmessage = (e: MessageEvent<string>) => {
      let frame: InboundFrame;
      try {
        frame = JSON.parse(e.data) as InboundFrame;
      } catch {
        return;
      }

      if (frame.type === 'ready') {
        callbacks.onSessionId(frame.session_id);
        callbacks.onStatus('ready');
        pingTimer = setInterval(() => {
          ws?.send(JSON.stringify({ type: 'ping' }));
        }, 25_000);
      } else if (frame.type === 'typing') {
        callbacks.onStatus('typing');
      } else if (frame.type === 'response') {
        callbacks.onMessage(frame.content);
        callbacks.onStatus('ready');
      } else if (frame.type === 'error') {
        callbacks.onError(frame.message);
        callbacks.onStatus('ready');
      }
      // pong: no-op
    };

    ws.onclose = () => {
      _clearTimers();
      if (!destroyed) {
        callbacks.onStatus('disconnected');
        reconnectTimer = setTimeout(connect, 3_000);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  function send(content: string) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'message', content }));
    }
  }

  function disconnect() {
    destroyed = true;
    _clearTimers();
    ws?.close();
  }

  function _clearTimers() {
    if (pingTimer !== null) { clearInterval(pingTimer); pingTimer = null; }
    if (reconnectTimer !== null) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  }

  return { connect, send, disconnect };
}
