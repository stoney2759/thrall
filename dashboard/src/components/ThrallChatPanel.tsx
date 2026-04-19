// ============================================================
// ThrallChatPanel.tsx
//
// Governed chat: only HUMAN → THRALL direction permitted.
// Both IDs sourced from app store — never hardcoded.
// Displays used_llm, provider, model_used from response.
//
// Features:
//   - Chat history persisted to localStorage (survives tab switches)
//   - Message queuing: send multiple messages without waiting
// ============================================================

import React, { useState, useRef, useEffect } from "react";
import { thrallChat } from "../api/client";
import { useAppStore } from "../state/store";
import type { ThrallChatResponse } from "../api/types";

interface ChatMessage {
  id: string;
  role: "human" | "thrall" | "error";
  text: string;
  meta?: {
    used_llm: boolean;
    provider?: string;
    model_used?: string;
  };
  ts: string;
}

const STORAGE_KEY = "thrall-chat-messages";

function loadMessages(): ChatMessage[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function now() {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

export function ThrallChatPanel() {
  const { humanNode, cooNode } = useAppStore();

  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [input, setInput] = useState("");
  const [queue, setQueue] = useState<string[]>([]);
  const [processing, setProcessing] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  // Auto-scroll on new messages or thinking indicator
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, processing]);

  // Process queue sequentially
  useEffect(() => {
    if (processing || queue.length === 0 || !humanNode || !cooNode) return;

    const [next, ...rest] = queue;
    setQueue(rest);
    setProcessing(true);

    thrallChat({
      human_node_id: humanNode.id,
      thrall_node_id: cooNode.id,
      prompt: next,
    }).then((result) => {
      setProcessing(false);

      if (!result.ok) {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: "error",
            text: `KERNEL ERROR: ${result.error}`,
            ts: now(),
          },
        ]);
        return;
      }

      const res: ThrallChatResponse = result.data;
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "thrall",
          text: res.reply_text,
          meta: {
            used_llm: res.used_llm,
            provider: res.provider,
            model_used: res.model_used,
          },
          ts: now(),
        },
      ]);
    });
  }, [processing, queue, humanNode, cooNode]);

  if (!humanNode || !cooNode) {
    return (
      <div className="panel thrall-chat-panel">
        <div className="panel-header">
          <span className="panel-title">THRALL CHANNEL</span>
          <span className="status-dot offline" />
        </div>
        <div className="panel-body">
          <div className="empty-state">Org not bootstrapped.</div>
        </div>
      </div>
    );
  }

  const handleSend = () => {
    const prompt = input.trim();
    if (!prompt) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "human",
      text: prompt,
      ts: now(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setQueue((q) => [...q, prompt]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClear = () => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const queuedCount = queue.length;

  return (
    <div className="panel thrall-chat-panel">
      <div className="panel-header">
        <span className="panel-title">THRALL CHANNEL</span>
        <div className="chat-participants">
          <span className="participant human">{humanNode.name}</span>
          <span className="participant-arrow">→</span>
          <span className="participant coo">{cooNode.name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {(processing || queuedCount > 0) && (
            <span style={{ fontSize: "11px", color: "var(--accent)", opacity: 0.8 }}>
              {queuedCount > 0 ? `${queuedCount + 1} queued` : "processing…"}
            </span>
          )}
          <button
            className="btn-ghost"
            onClick={handleClear}
            style={{ fontSize: "11px", padding: "2px 8px" }}
            title="Clear chat history"
          >
            CLEAR
          </button>
          <span className="status-dot online" />
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            Secure channel open. HUMAN → THRALL only.
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-msg chat-msg-${msg.role}`}>
            <div className="chat-msg-header">
              <span className="chat-msg-role">
                {msg.role === "human"
                  ? humanNode.name
                  : msg.role === "thrall"
                  ? cooNode.name
                  : "SYSTEM"}
              </span>
              <span className="chat-msg-ts">{msg.ts}</span>
            </div>
            <div className="chat-msg-body">{msg.text}</div>
            {msg.meta && (
              <div className="chat-msg-meta">
                {msg.meta.used_llm
                  ? `via ${msg.meta.provider ?? "?"} / ${msg.meta.model_used ?? "?"}`
                  : "context/memory only (no LLM)"}
              </div>
            )}
          </div>
        ))}
        {processing && (
          <div className="chat-msg chat-msg-thrall chat-msg-thinking">
            <div className="chat-msg-header">
              <span className="chat-msg-role">{cooNode.name}</span>
              {queuedCount > 0 && (
                <span className="chat-msg-ts">{queuedCount} more queued</span>
              )}
            </div>
            <div className="chat-msg-body">
              <span className="thinking-dots">
                <span />
                <span />
                <span />
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message Thrall… (Enter to send, queue supported)"
          rows={2}
        />
        <button
          className="btn-primary chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim()}
        >
          SEND
        </button>
      </div>
    </div>
  );
}
