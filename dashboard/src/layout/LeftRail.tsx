// ============================================================
// LeftRail.tsx — Fixed left navigation rail
// Grouped by: Core | Agent | Settings | Resources
// Collapsible to icon-only mode
// Logo click → returns to Chat (home)
// ============================================================

import React from "react";
import {
  MessageSquare, Sliders, GitBranch, CheckSquare, Activity,
  Cpu, Shield, Clock, Database, Zap, BarChart2,
  Settings, Terminal, FileText, Box, BookOpen,
  ChevronLeft, ChevronRight,
} from "lucide-react";
import type { AppId, NavGroup } from "../config/apps.config";
import { APPS, APP_GROUPS } from "../config/apps.config";
import { useAppStore } from "../state/store";

const ICONS: Record<string, React.ComponentType<{ size?: number; strokeWidth?: number }>> = {
  MessageSquare, Sliders, GitBranch, CheckSquare, Activity,
  Cpu, Shield, Clock, Database, Zap, BarChart2,
  Settings, Terminal, FileText, Box, BookOpen,
};

function AppIcon({ name, size = 15 }: { name: string; size?: number }) {
  const Icon = ICONS[name];
  if (!Icon) return <span style={{ width: size, height: size, display: "inline-block" }} />;
  return <Icon size={size} strokeWidth={1.5} />;
}

export function LeftRail() {
  const { activeApp, setActiveApp, railCollapsed, toggleRail } = useAppStore();

  const groupedApps = APP_GROUPS.map((group) => ({
    ...group,
    apps: APPS.filter((a) => a.group === (group.id as NavGroup)),
  }));

  const handleLogoClick = () => {
    setActiveApp("chat");
  };

  return (
    <aside className={`left-rail ${railCollapsed ? "collapsed" : ""}`}>
      {/* Rail header */}
      <div className="rail-header">
        {!railCollapsed && (
          <button
            className="rail-logo rail-logo-btn"
            onClick={handleLogoClick}
            title="Return to Chat"
            aria-label="Return to home"
          >
            <span className="rail-logo-mark">◈</span>
            <span className="rail-logo-text">OpenThrall</span>
          </button>
        )}
        {railCollapsed && (
          <button
            className="rail-logo-icon-btn"
            onClick={handleLogoClick}
            title="Return to Chat"
            aria-label="Return to home"
          >
            <span className="rail-logo-mark">◈</span>
          </button>
        )}
        <button
          className="rail-toggle"
          onClick={toggleRail}
          aria-label={railCollapsed ? "Expand navigation" : "Collapse navigation"}
          title={railCollapsed ? "Expand" : "Collapse"}
        >
          {railCollapsed ? <ChevronRight size={14} strokeWidth={1.5} /> : <ChevronLeft size={14} strokeWidth={1.5} />}
        </button>
      </div>

      {/* Nav groups */}
      <nav className="rail-nav">
        {groupedApps.map((group) => (
          <div key={group.id} className="rail-group">
            {!railCollapsed && (
              <div className="rail-group-label">{group.label}</div>
            )}
            {group.apps.map((app) => (
              <button
                key={app.id}
                className={`rail-item ${activeApp === app.id ? "active" : ""} ${app.status === "placeholder" ? "placeholder" : ""}`}
                onClick={() => setActiveApp(app.id)}
                title={railCollapsed ? app.label : undefined}
                aria-label={app.label}
              >
                <span className="rail-item-icon">
                  <AppIcon name={app.icon} size={15} />
                </span>
                {!railCollapsed && (
                  <span className="rail-item-label">{app.label}</span>
                )}
                {!railCollapsed && app.status === "placeholder" && (
                  <span className="rail-item-soon">soon</span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
