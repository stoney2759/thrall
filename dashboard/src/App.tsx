import { useEffect, useRef } from 'react';
import { useStore } from './store';
import { createWsClient } from './ws';
import type { WsClient } from './ws';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ControlPanel from './components/ControlPanel';
import AgentsPanel from './components/AgentsPanel';
import SchedulerPanel from './components/SchedulerPanel';
import LogsPanel from './components/LogsPanel';
import MemoryPanel from './components/MemoryPanel';
import SessionsPanel from './components/SessionsPanel';

export default function App() {
  const { activePanel, setWsStatus, addMessage, setSessionId, wsStatus } = useStore();
  const wsRef = useRef<WsClient | null>(null);

  useEffect(() => {
    const token = (import.meta as unknown as { env: Record<string, string> }).env.VITE_THRALL_TOKEN ?? '';
    const client = createWsClient(token, {
      onStatus: setWsStatus,
      onMessage: (content) => addMessage('assistant', content),
      onError: (msg) => addMessage('assistant', `[error] ${msg}`),
      onSessionId: setSessionId,
    });
    wsRef.current = client;
    client.connect();
    return () => client.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function sendMessage(content: string) {
    addMessage('user', content);
    wsRef.current?.send(content);
  }

  return (
    <div className="flex h-screen bg-base text-primary overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {activePanel === 'chat' && (
          <Chat onSend={sendMessage} typing={wsStatus === 'typing'} />
        )}
        {activePanel === 'control' && <ControlPanel />}
        {activePanel === 'agents' && <AgentsPanel />}
        {activePanel === 'scheduler' && <SchedulerPanel />}
        {activePanel === 'logs' && <LogsPanel />}
        {activePanel === 'memory' && <MemoryPanel />}
        {activePanel === 'sessions' && <SessionsPanel />}
      </div>
    </div>
  );
}
