import { useEffect, useMemo, useRef, useState } from 'react';
import { Send, RotateCcw, Plus, Paperclip, X, Link2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useStore } from '../store';
import type { Session } from '../store';

interface Props {
  onSend: (content: string) => void;
  typing: boolean;
}

interface AttachedImage {
  name: string;
  dataUrl: string;
}

interface CommandEntry {
  name: string;
  description: string;
}

const IMG_BLOCK = /\[Image: ([^\]]+)\]\n(data:image\/[^\s]+)/g;

const USER_MD_COMPONENTS = {
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mb-1 last:mb-0">{children}</p>
  ),
  code: ({ inline, children }: { inline?: boolean; children?: React.ReactNode }) =>
    inline ? (
      <code className="bg-black/20 rounded px-1 py-0.5 font-mono text-xs">{children}</code>
    ) : (
      <pre className="bg-black/20 rounded-lg px-3 py-2 my-1.5 font-mono text-xs overflow-x-auto whitespace-pre">
        <code>{children}</code>
      </pre>
    ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-disc pl-4 mb-1 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal pl-4 mb-1 space-y-0.5">{children}</ol>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto my-2">
      <table className="text-xs border-collapse w-full">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="border border-border px-2 py-1 text-left font-medium text-muted bg-surface">{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="border border-border px-2 py-1">{children}</td>
  ),
};

function renderUserContent(content: string) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  IMG_BLOCK.lastIndex = 0;
  while ((match = IMG_BLOCK.exec(content)) !== null) {
    if (match.index > last) {
      const text = content.slice(last, match.index);
      parts.push(
        <ReactMarkdown key={last} remarkPlugins={[remarkGfm]} components={USER_MD_COMPONENTS}>{text}</ReactMarkdown>
      );
    }
    parts.push(
      <div key={match.index} className="mt-2">
        <img
          src={match[2]}
          alt={match[1]}
          className="max-w-[240px] max-h-[180px] rounded-lg border border-border object-cover"
        />
        <p className="text-xs text-muted mt-1">{match[1]}</p>
      </div>,
    );
    last = match.index + match[0].length;
  }
  if (last < content.length) {
    parts.push(
      <ReactMarkdown key={last} components={USER_MD_COMPONENTS}>{content.slice(last)}</ReactMarkdown>
    );
  }
  return parts.length > 0 ? parts : <ReactMarkdown remarkPlugins={[remarkGfm]} components={USER_MD_COMPONENTS}>{content}</ReactMarkdown>;
}

const EXT_TO_LANG: Record<string, string> = {
  py: 'python', js: 'javascript', ts: 'typescript',
  jsx: 'javascript', tsx: 'typescript', json: 'json',
  yaml: 'yaml', yml: 'yaml', toml: 'toml', md: 'markdown',
  html: 'html', css: 'css', xml: 'xml', sh: 'bash',
};

interface SessionTabProps {
  session: Session;
  active: boolean;
  isMain: boolean;
  onSwitch: (id: string) => void;
  onClose: (id: string) => void;
  onRename: (id: string, name: string) => void;
}

function SessionTab({ session, active, isMain, onSwitch, onClose, onRename }: SessionTabProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.name);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit(e: React.MouseEvent) {
    e.stopPropagation();
    setDraft(session.name);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commitEdit() {
    if (draft.trim()) onRename(session.id, draft.trim());
    setEditing(false);
  }

  return (
    <div
      onClick={() => onSwitch(session.id)}
      onDoubleClick={startEdit}
      className={`group flex items-center gap-1.5 px-3 py-2.5 text-xs cursor-pointer border-r border-border flex-shrink-0 select-none transition-colors ${
        active
          ? 'text-primary bg-elevated'
          : 'text-muted hover:text-primary hover:bg-elevated/50'
      }`}
    >
      {editing ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitEdit();
            if (e.key === 'Escape') setEditing(false);
          }}
          onClick={(e) => e.stopPropagation()}
          className="bg-transparent outline-none w-24 text-primary"
          autoFocus
        />
      ) : (
        <>
          <span className="max-w-[100px] truncate">{session.name}</span>
          {isMain && <span title="Linked to Telegram"><Link2 size={10} className="text-zinc-500 flex-shrink-0" /></span>}
        </>
      )}
      {!isMain && (
        <button
          onClick={(e) => { e.stopPropagation(); onClose(session.id); }}
          className={`transition-colors flex-shrink-0 rounded ${
            active
              ? 'text-muted hover:text-primary'
              : 'opacity-0 group-hover:opacity-100 text-muted hover:text-primary'
          }`}
        >
          <X size={10} />
        </button>
      )}
    </div>
  );
}

export default function Chat({ onSend, typing }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!typing) { setElapsed(0); return; }
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 250);
    return () => clearInterval(id);
  }, [typing]);

  const {
    messages, clearChat,
    sessions, activeSessionId,
    newSession, switchSession, renameSession, deleteSession,
  } = useStore();


  const [input, setInput] = useState('');
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [commands, setCommands] = useState<CommandEntry[]>([]);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [cmdIndex, setCmdIndex] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const paletteRef = useRef<HTMLDivElement>(null);

  // Load draft for this session when session changes
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`thrall_draft_${activeSessionId}`) ?? '';
      setInput(saved);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        if (saved) textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
      }
    } catch { /* ignore */ }
  }, [activeSessionId]);

  // Persist draft on every keystroke
  useEffect(() => {
    if (!activeSessionId) return;
    try {
      if (input) localStorage.setItem(`thrall_draft_${activeSessionId}`, input);
      else localStorage.removeItem(`thrall_draft_${activeSessionId}`);
    } catch { /* ignore */ }
  }, [input, activeSessionId]);

  // /approve button — replaces the paragraph in assistant messages
  const mdComponents = useMemo(() => ({
    p({ children }: { children?: React.ReactNode }) {
      const text = (Array.isArray(children) ? children : [children])
        .map((c) => (typeof c === 'string' ? c : ''))
        .join('')
        .trim();
      if (text === '/approve') {
        return (
          <button
            onClick={() => onSend('/approve')}
            className="mt-2 inline-flex items-center px-3 py-1.5 rounded-lg bg-accent/20 text-accent border border-accent/30 text-xs font-mono hover:bg-accent/30 active:scale-95 transition-all cursor-pointer"
          >
            /approve
          </button>
        );
      }
      return <p>{children}</p>;
    },
    table: ({ children }: { children?: React.ReactNode }) => (
      <div className="overflow-x-auto my-2">
        <table className="text-xs border-collapse w-full">{children}</table>
      </div>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
      <th className="border border-border px-2 py-1 text-left font-medium text-muted bg-surface">{children}</th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
      <td className="border border-border px-2 py-1">{children}</td>
    ),
  }), [onSend]);

  useEffect(() => {
    fetch('/api/commands')
      .then((r) => r.json())
      .then((data) => setCommands(data as CommandEntry[]))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  // Compute filtered commands whenever input changes
  const cmdQuery = input.startsWith('/') ? input.slice(1).toLowerCase() : '';
  const filteredCmds = cmdQuery !== undefined && input.startsWith('/')
    ? commands.filter((c) => c.name.startsWith(cmdQuery))
    : [];

  // Keep index in bounds when filter changes
  useEffect(() => {
    setCmdIndex(0);
  }, [cmdQuery]);

  // Scroll active item into view
  useEffect(() => {
    if (!cmdOpen || filteredCmds.length === 0) return;
    const item = paletteRef.current?.children[cmdIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [cmdIndex, cmdOpen, filteredCmds.length]);

  function selectCmd(cmd: CommandEntry) {
    setInput(`/${cmd.name} `);
    setCmdOpen(false);
    textareaRef.current?.focus();
  }

  function submit() {
    const trimmed = input.trim();
    if (!trimmed && attachedImages.length === 0) return;

    let content = trimmed;
    if (attachedImages.length > 0) {
      const imgBlocks = attachedImages
        .map((img) => `[Image: ${img.name}]\n${img.dataUrl}`)
        .join('\n\n');
      content = trimmed ? `${trimmed}\n\n${imgBlocks}` : imgBlocks;
      setAttachedImages([]);
    }

    setInput('');
    setCmdOpen(false);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    try { localStorage.removeItem(`thrall_draft_${activeSessionId}`); } catch { /* ignore */ }
    onSend(content);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (cmdOpen && filteredCmds.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setCmdIndex((i) => Math.min(i + 1, filteredCmds.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setCmdIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && filteredCmds.length > 0 && input !== `/${filteredCmds[cmdIndex]?.name}`)) {
        e.preventDefault();
        if (filteredCmds[cmdIndex]) selectCmd(filteredCmds[cmdIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setCmdOpen(false);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function onInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setInput(val);
    setCmdOpen(val.startsWith('/'));
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function onFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    const reader = new FileReader();

    if (file.type.startsWith('image/')) {
      reader.onload = () => {
        setAttachedImages((prev) => [
          ...prev,
          { name: file.name, dataUrl: reader.result as string },
        ]);
      };
      reader.readAsDataURL(file);
    } else {
      reader.onload = () => {
        const content = reader.result as string;
        const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
        const lang = EXT_TO_LANG[ext] ?? '';
        const block = `[File: ${file.name}]\n\`\`\`${lang}\n${content.slice(0, 50_000)}\n\`\`\`\n\n`;
        setInput((prev) => block + prev);
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
          }
        }, 0);
      };
      reader.readAsText(file);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Session tabs */}
      <div className="flex items-center border-b border-border overflow-x-auto flex-shrink-0">
        {sessions.map((s, i) => (
          <SessionTab
            key={s.id}
            session={s}
            active={s.id === activeSessionId}
            isMain={i === 0}
            onSwitch={switchSession}
            onClose={deleteSession}
            onRename={renameSession}
          />
        ))}
        <button
          onClick={newSession}
          title="New session"
          className="px-3 py-2.5 text-muted hover:text-primary transition-colors flex-shrink-0"
        >
          <Plus size={12} />
        </button>
        <div className="ml-auto pr-4 flex items-center gap-3">
          <button
            onClick={clearChat}
            title="Clear chat"
            className="text-muted hover:text-primary transition-colors"
          >
            <RotateCcw size={12} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center select-none">
            <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
              <span className="text-2xl font-bold text-accent">T</span>
            </div>
            <p className="text-primary font-medium text-sm">Thrall</p>
            <p className="text-muted text-sm max-w-xs leading-relaxed">
              Your autonomous AI assistant. Send a message to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-6 max-w-3xl mx-auto">
            {messages.map((msg) =>
              msg.role === 'user' ? (
                <div key={msg.id} className="flex flex-col items-end gap-0.5">
                  <span className="text-xs text-muted px-1 select-none">You</span>
                  <div className="bg-elevated rounded-2xl rounded-tr-md px-4 py-2.5 text-primary text-sm max-w-xl break-words">
                    {renderUserContent(msg.content)}
                  </div>
                </div>
              ) : (
                <div key={msg.id} className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-xs font-bold text-accent select-none">T</span>
                  </div>
                  <div className="flex flex-col flex-1 min-w-0">
                    <span className="text-xs text-accent font-medium mb-1 select-none">Thrall</span>
                    <div className="prose-thrall text-primary text-sm leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ),
            )}

            {typing && (
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-bold text-accent select-none">T</span>
                </div>

                {/* OPTION 1 — 5 balls, bounce */}
                {/* <div className="flex gap-1 pt-2.5">
                  {[0, 100, 200, 300, 400].map((delay) => (
                    <span
                      key={delay}
                      className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </div> */}

                {/* OPTION 3 — Torus of dots (parametric, R=7 major, r=3 tube, 14×6 grid) */}
                <div className="flex items-center gap-2 pt-1.5">
                <div style={{ transform: 'rotateZ(-30deg)' }}>
                <div style={{ perspective: '120px' }}>
                  <div
                    className="relative animate-torus-spin"
                    style={{ width: '22px', height: '22px', transformStyle: 'preserve-3d' }}
                  >
                    {Array.from({ length: 14 }).flatMap((_, ti) =>
                      Array.from({ length: 6 }).map((_, pi) => {
                        const theta = (ti / 14) * Math.PI * 2;
                        const phi = (pi / 6) * Math.PI * 2;
                        const R = 7;
                        const r = 3;
                        const x = (R + r * Math.cos(phi)) * Math.cos(theta);
                        const y = (R + r * Math.cos(phi)) * Math.sin(theta);
                        const z = r * Math.sin(phi);
                        return (
                          <span
                            key={`${ti}-${pi}`}
                            className="absolute rounded-full bg-muted"
                            style={{
                              width: '2px', height: '2px',
                              top: 'calc(50% - 1px)', left: 'calc(50% - 1px)',
                              transform: `translate3d(${x}px, ${y}px, ${z}px)`,
                            }}
                          />
                        );
                      })
                    )}
                  </div>
                </div>
                </div>
                {typing && (
                  <span className="text-xs text-muted tabular-nums select-none">
                    {elapsed >= 60 ? `${Math.floor(elapsed / 60)}m ${elapsed % 60}s` : `${elapsed}s`}
                  </span>
                )}
                </div>

                {/* OPTION 2 — Newton's cradle */}
                {/* <div className="flex gap-1 pt-2.5">
                  <span className="w-[4.5px] h-[4.5px] rounded-full bg-muted animate-cradle-left" />
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="w-[4.5px] h-[4.5px] rounded-full bg-muted" />
                  ))}
                  <span className="w-[4.5px] h-[4.5px] rounded-full bg-muted animate-cradle-right" />
                </div> */}

                {/* DEFAULT — 3 balls bounce (original)
                <div className="flex gap-1 pt-2.5">
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </div> */}

              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="px-4 pb-5 flex-shrink-0 max-w-3xl mx-auto w-full">
        {/* Image previews */}
        {attachedImages.length > 0 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            {attachedImages.map((img, i) => (
              <div key={i} className="relative">
                <img
                  src={img.dataUrl}
                  alt={img.name}
                  className="w-16 h-16 object-cover rounded-lg border border-border"
                />
                <button
                  onClick={() => setAttachedImages((prev) => prev.filter((_, j) => j !== i))}
                  className="absolute -top-1 -right-1 w-4 h-4 bg-zinc-800 border border-border rounded-full flex items-center justify-center text-muted hover:text-primary"
                >
                  <X size={9} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Command palette — floats above input */}
        <div className="relative">
          {cmdOpen && filteredCmds.length > 0 && (
            <div
              ref={paletteRef}
              className="absolute bottom-full mb-2 left-0 right-0 bg-elevated border border-border rounded-xl shadow-xl overflow-hidden max-h-64 overflow-y-auto z-50"
            >
              {filteredCmds.map((cmd, i) => (
                <button
                  key={cmd.name}
                  onMouseDown={(e) => { e.preventDefault(); selectCmd(cmd); }}
                  className={`w-full flex items-baseline gap-3 px-4 py-2.5 text-left transition-colors ${
                    i === cmdIndex
                      ? 'bg-accent/15 text-primary'
                      : 'text-primary hover:bg-surface'
                  }`}
                >
                  <span className="text-accent text-sm font-mono font-medium flex-shrink-0">
                    /{cmd.name}
                  </span>
                  <span className="text-muted text-xs truncate">{cmd.description}</span>
                </button>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2 bg-elevated rounded-2xl border border-border px-3 py-3">
            {/* Upload */}
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".txt,.md,.py,.js,.ts,.jsx,.tsx,.json,.yaml,.yml,.toml,.html,.css,.xml,.csv,.pdf,.png,.jpg,.jpeg,.gif,.webp"
              onChange={onFileSelect}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              title="Attach file"
              className="text-muted hover:text-primary transition-colors flex-shrink-0 mb-0.5"
            >
              <Paperclip size={15} />
            </button>

            <textarea
              ref={textareaRef}
              value={input}
              onChange={onInput}
              onKeyDown={onKeyDown}
              placeholder="Message Thrall…"
              rows={1}
              className="flex-1 bg-transparent text-primary text-sm resize-none outline-none placeholder-muted leading-relaxed"
              style={{ minHeight: '1.25rem' }}
            />
            <button
              onClick={submit}
              className="w-7 h-7 rounded-lg bg-accent hover:bg-accent-hover flex items-center justify-center transition-colors flex-shrink-0"
            >
              <Send size={13} className="text-white" />
            </button>
          </div>
        </div>
        <p className="text-center text-muted text-xs mt-2 select-none">
          Enter to send · Shift+Enter for new line · Tab to complete command
        </p>
      </div>
    </div>
  );
}
