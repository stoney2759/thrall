import { create } from 'zustand';
import type { WsStatus } from './ws';

export type MsgRole = 'user' | 'assistant';
export type Panel = 'chat' | 'control' | 'agents' | 'scheduler' | 'logs' | 'memory' | 'sessions';

export interface ChatMessage {
  id: string;
  role: MsgRole;
  content: string;
  ts: number;
}

export interface Session {
  id: string;
  name: string;
  messages: ChatMessage[];
  createdAt: number;
}

function _loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem('thrall_sessions');
    if (raw) return JSON.parse(raw) as Session[];
  } catch {}
  return [];
}

function _saveSessions(sessions: Session[]): void {
  try {
    localStorage.setItem('thrall_sessions', JSON.stringify(sessions));
  } catch {}
}

function _makeSession(name = 'New chat'): Session {
  return { id: crypto.randomUUID(), name, messages: [], createdAt: Date.now() };
}

const _saved = _loadSessions();
const _initSessions = _saved.length > 0 ? _saved : [_makeSession('Chat')];
const _initActiveId = _initSessions[0].id;

interface Store {
  messages: ChatMessage[];
  wsStatus: WsStatus;
  sessionId: string | null;
  activePanel: Panel;
  sessions: Session[];
  activeSessionId: string;

  addMessage: (role: MsgRole, content: string) => void;
  setWsStatus: (s: WsStatus) => void;
  setSessionId: (id: string) => void;
  setPanel: (p: Panel) => void;
  clearChat: () => void;
  newSession: () => void;
  switchSession: (id: string) => void;
  renameSession: (id: string, name: string) => void;
  deleteSession: (id: string) => void;
}

export const useStore = create<Store>((set) => ({
  messages: _initSessions.find((s) => s.id === _initActiveId)?.messages ?? [],
  wsStatus: 'disconnected',
  sessionId: null,
  activePanel: 'chat',
  sessions: _initSessions,
  activeSessionId: _initActiveId,

  addMessage: (role, content) => {
    const msg: ChatMessage = { id: crypto.randomUUID(), role, content, ts: Date.now() };
    set((s) => {
      const sessions = s.sessions.map((sess) => {
        if (sess.id !== s.activeSessionId) return sess;
        const updated = { ...sess, messages: [...sess.messages, msg] };
        // Auto-name from first user message
        if (role === 'user' && sess.messages.length === 0 && sess.name === 'New chat') {
          updated.name = content.slice(0, 28) + (content.length > 28 ? '…' : '');
        }
        return updated;
      });
      _saveSessions(sessions);
      return { sessions, messages: [...s.messages, msg] };
    });
  },

  setWsStatus: (wsStatus) => set({ wsStatus }),
  setSessionId: (sessionId) => set({ sessionId }),
  setPanel: (activePanel) => set({ activePanel }),

  clearChat: () =>
    set((s) => {
      const sessions = s.sessions.map((sess) =>
        sess.id === s.activeSessionId ? { ...sess, messages: [] } : sess,
      );
      _saveSessions(sessions);
      return { sessions, messages: [] };
    }),

  newSession: () =>
    set((s) => {
      const sess = _makeSession();
      const sessions = [sess, ...s.sessions];
      _saveSessions(sessions);
      return { sessions, activeSessionId: sess.id, messages: [] };
    }),

  switchSession: (id) =>
    set((s) => {
      const sess = s.sessions.find((x) => x.id === id);
      if (!sess) return {};
      return { activeSessionId: id, messages: sess.messages };
    }),

  renameSession: (id, name) =>
    set((s) => {
      const sessions = s.sessions.map((sess) =>
        sess.id === id ? { ...sess, name } : sess,
      );
      _saveSessions(sessions);
      return { sessions };
    }),

  deleteSession: (id) =>
    set((s) => {
      const sessions = s.sessions.filter((sess) => sess.id !== id);
      if (sessions.length === 0) {
        const fresh = _makeSession('Chat');
        _saveSessions([fresh]);
        return { sessions: [fresh], activeSessionId: fresh.id, messages: [] };
      }
      const nextId = s.activeSessionId === id ? sessions[0].id : s.activeSessionId;
      const nextMsgs = sessions.find((sess) => sess.id === nextId)?.messages ?? [];
      _saveSessions(sessions);
      return { sessions, activeSessionId: nextId, messages: nextMsgs };
    }),
}));
