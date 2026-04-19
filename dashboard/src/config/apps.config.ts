// ============================================================
// apps.config.ts — Single source of truth for navigation
// Adding a new app = add one entry here. No structural changes needed.
// ============================================================

export type AppStatus = "live" | "placeholder";

export interface AppDef {
  id: AppId;
  label: string;
  icon: string;       // lucide-react icon name
  status: AppStatus;
  group: NavGroup;
}

export interface ToolbarView {
  id: string;
  label: string;
}

export type AppId =
  | "chat"
  | "control"
  | "org"
  | "approvals"
  | "events"
  | "agents"
  | "governance"
  | "logs"
  | "cron"
  | "memory"
  | "workspace"
  | "config"
  | "debug"
  | "llm"
  | "analytics"
  | "sandbox"
  | "docs";

export type NavGroup = "core" | "agent" | "settings" | "resources";

export const APPS: AppDef[] = [
  // Core
  { id: "chat",       label: "Chat",       icon: "MessageSquare", status: "live",        group: "core"      },
  { id: "control",    label: "Control",    icon: "Sliders",       status: "live",        group: "core"      },
  { id: "org",        label: "Org",        icon: "GitBranch",     status: "live",        group: "core"      },
  { id: "approvals",  label: "Approvals",  icon: "CheckSquare",   status: "live",        group: "core"      },
  { id: "events",     label: "Events",     icon: "Activity",      status: "live",        group: "core"      },
  // Agent
  { id: "agents",     label: "Agents",     icon: "Cpu",           status: "live",        group: "agent"     },
  { id: "governance", label: "Governance", icon: "Shield",        status: "live",        group: "agent"     },
  { id: "cron",       label: "Cron",       icon: "Clock",         status: "live",        group: "agent"     },
  { id: "memory",     label: "Memory",     icon: "Database",      status: "placeholder", group: "agent"     },
  { id: "workspace",  label: "Workspace",  icon: "FileText",      status: "live",        group: "agent"     },
  { id: "llm",        label: "LLM",        icon: "Zap",           status: "placeholder", group: "agent"     },
  { id: "analytics",  label: "Analytics",  icon: "BarChart2",     status: "placeholder", group: "agent"     },
  // Settings
  { id: "config",     label: "Config",     icon: "Settings",      status: "live",        group: "settings"  },
  { id: "debug",      label: "Debug",      icon: "Terminal",      status: "live",        group: "settings"  },
  { id: "logs",       label: "Logs",       icon: "FileText",      status: "live",        group: "settings"  },
  // Resources
  { id: "sandbox",    label: "Sandbox",    icon: "Box",           status: "placeholder", group: "resources" },
  { id: "docs",       label: "Docs",       icon: "BookOpen",      status: "live",        group: "resources" },
];

export const APP_GROUPS: { id: NavGroup; label: string }[] = [
  { id: "core",      label: "Core"      },
  { id: "agent",     label: "Agent"     },
  { id: "settings",  label: "Settings"  },
  { id: "resources", label: "Resources" },
];

// ── Contextual toolbar definitions ─────────────────────────

export const TOOLBAR_VIEWS: Record<AppId, ToolbarView[]> = {
  chat:       [
    { id: "sessions",  label: "Sessions"  },
    { id: "channels",  label: "Channels"  },
    { id: "instances", label: "Instances" },
  ],
  control:    [
    { id: "overview",  label: "Overview"  },
    { id: "jobs",      label: "Jobs"      },
    { id: "cron",      label: "Cron"      },
    { id: "health",    label: "Health"    },
    { id: "activity",  label: "Activity"  },
  ],
  org:        [
    { id: "hierarchy", label: "Hierarchy" },
    { id: "nodes",     label: "Nodes"     },
    { id: "workspace", label: "Workspace" },
    { id: "policies",  label: "Policies"  },
  ],
  approvals:  [
    { id: "pending",   label: "Pending"   },
    { id: "history",   label: "History"   },
  ],
  events:     [
    { id: "live",      label: "Live Feed" },
    { id: "audit",     label: "Audit"     },
  ],
  agents:     [
    { id: "list",      label: "All Agents" },
    { id: "active",    label: "Active"     },
    { id: "detail",    label: "Detail"     },
  ],
  governance: [
    { id: "overview",  label: "Overview"  },
    { id: "rules",     label: "Rules"     },
    { id: "audit",     label: "Audit"     },
  ],
  logs:       [
    { id: "system",    label: "System"    },
    { id: "errors",    label: "Errors"    },
    { id: "access",    label: "Access"    },
  ],
  cron:       [
    { id: "scheduled", label: "Scheduled" },
    { id: "history",   label: "History"   },
  ],
  memory:     [
    { id: "store",     label: "Store"     },
    { id: "graph",     label: "Graph"     },
  ],
  workspace:  [
    { id: "browse",    label: "Files"     },
    { id: "edit",      label: "Editor"    },
  ],
  config:     [
    { id: "system",    label: "System"    },
    { id: "nodes",     label: "Nodes"     },
    { id: "llm",       label: "LLM"       },
  ],
  debug:      [
    { id: "console",   label: "Console"   },
    { id: "requests",  label: "Requests"  },
    { id: "state",     label: "State"     },
  ],
  llm:        [
    { id: "providers", label: "Providers" },
    { id: "usage",     label: "Usage"     },
    { id: "models",    label: "Models"    },
  ],
  analytics:  [
    { id: "overview",  label: "Overview"  },
    { id: "usage",     label: "Usage"     },
  ],
  sandbox:    [
    { id: "ai",        label: "AI Echo"   },
    { id: "tools",     label: "Tools"     },
  ],
  docs:       [
    { id: "overview",  label: "Overview"  },
    { id: "api",       label: "API Ref"   },
    { id: "guide",     label: "Guide"     },
  ],
};

export function getDefaultView(appId: AppId): string {
  return TOOLBAR_VIEWS[appId]?.[0]?.id ?? "";
}
