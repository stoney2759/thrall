// ============================================================
// ContentArea.tsx — Renders the active app/view component
// Pure routing — no logic lives here
// ============================================================

import React from "react";
import { useAppStore } from "../state/store";

// App imports
import { ChatApp } from "../apps/chat/ChatApp";
import { ControlApp } from "../apps/control/ControlApp";
import { OrgApp } from "../apps/org/OrgApp";
import { ApprovalsApp } from "../apps/approvals/ApprovalsApp";
import { EventsApp } from "../apps/events/EventsApp";
import { AgentsApp } from "../apps/agents/AgentsApp";
import { GovernanceApp } from "../apps/governance/GovernanceApp";
import { LogsApp } from "../apps/logs/LogsApp";
import { CronApp } from "../apps/cron/CronApp";
import { MemoryApp } from "../apps/memory/MemoryApp";
import { ConfigApp } from "../apps/config-app/ConfigApp";
import { DebugApp } from "../apps/debug/DebugApp";
import { LlmApp } from "../apps/llm/LlmApp";
import { AnalyticsApp } from "../apps/analytics/AnalyticsApp";
import { SandboxApp } from "../apps/sandbox/SandboxApp";
import { DocsApp } from "../apps/docs/DocsApp";
import { WorkspaceApp } from "../apps/workspace/WorkspaceApp";

export function ContentArea() {
  const { activeApp, activeView } = useAppStore();

  const props = { activeView };

  const renderApp = () => {
    switch (activeApp) {
      case "chat":       return <ChatApp {...props} />;
      case "control":    return <ControlApp {...props} />;
      case "org":        return <OrgApp {...props} />;
      case "approvals":  return <ApprovalsApp {...props} />;
      case "events":     return <EventsApp {...props} />;
      case "agents":     return <AgentsApp {...props} />;
      case "governance": return <GovernanceApp {...props} />;
      case "logs":       return <LogsApp {...props} />;
      case "cron":       return <CronApp {...props} />;
      case "memory":     return <MemoryApp {...props} />;
      case "config":     return <ConfigApp {...props} />;
      case "debug":      return <DebugApp {...props} />;
      case "llm":        return <LlmApp {...props} />;
      case "analytics":  return <AnalyticsApp {...props} />;
      case "sandbox":    return <SandboxApp {...props} />;
      case "workspace":  return <WorkspaceApp {...props} />;
      case "docs":       return <DocsApp {...props} />;
      default:           return <div className="content-empty">Unknown app</div>;
    }
  };

  return (
    <main className="content-area">
      {renderApp()}
    </main>
  );
}
