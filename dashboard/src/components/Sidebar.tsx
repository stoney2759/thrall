import { MessageSquare, Activity, Bot, Clock, ScrollText, Brain, History } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useStore } from '../store';
import type { Panel } from '../store';

interface NavItem {
  id: Panel;
  Icon: LucideIcon;
  label: string;
}

const NAV: NavItem[] = [
  { id: 'chat',      Icon: MessageSquare, label: 'Chat' },
  { id: 'control',   Icon: Activity,      label: 'Control' },
  { id: 'agents',    Icon: Bot,           label: 'Agents' },
  { id: 'scheduler', Icon: Clock,         label: 'Scheduler' },
  { id: 'logs',      Icon: ScrollText,    label: 'Logs' },
  { id: 'memory',    Icon: Brain,         label: 'Memory' },
  { id: 'sessions',  Icon: History,       label: 'Sessions' },
];

export default function Sidebar() {
  const { activePanel, setPanel, wsStatus } = useStore();

  const dotColor =
    wsStatus === 'ready' || wsStatus === 'typing'
      ? 'bg-green-400'
      : wsStatus === 'connecting'
      ? 'bg-yellow-400'
      : 'bg-red-500';

  return (
    <nav className="w-14 flex flex-col items-center py-4 bg-sidebar border-r border-border flex-shrink-0">
      {/* Logo mark */}
      <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center mb-5">
        <span className="text-white text-sm font-bold select-none">T</span>
      </div>

      {/* Nav items */}
      <div className="flex flex-col gap-1 w-full px-2">
        {NAV.map(({ id, Icon, label }) => (
          <button
            key={id}
            onClick={() => setPanel(id)}
            title={label}
            className={`w-full h-9 rounded-lg flex items-center justify-center transition-colors ${
              activePanel === id
                ? 'bg-accent/20 text-accent'
                : 'text-muted hover:text-primary hover:bg-elevated'
            }`}
          >
            <Icon size={17} />
          </button>
        ))}
      </div>

      {/* Connection status dot */}
      <div className="mt-auto mb-1" title={wsStatus}>
        <div className={`w-2 h-2 rounded-full transition-colors ${dotColor}`} />
      </div>
    </nav>
  );
}
