// ============================================================
// App.tsx — Root. Checks /org, routes wizard ↔ AppShell.
// ============================================================

import React, { useEffect, useState } from "react";
import { AppStoreProvider, useAppStore } from "./state/store";
import { BootstrapWizard } from "./components/BootstrapWizard";
import { AppShell } from "./layout/AppShell";
import { getOrg } from "./api/client";
import type { CreateHumanResponse } from "./api/types";

function isBootstrapped(data: unknown): data is CreateHumanResponse {
  return (
    !!data &&
    typeof data === "object" &&
    "human" in data &&
    "coo" in data &&
    "org" in data
  );
}

function AppInner() {
  const store = useAppStore();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function checkOrg() {
      const result = await getOrg();
      if (result.ok && isBootstrapped(result.data)) {
        store.setBootstrapped(
          result.data.human,
          result.data.coo,
          result.data.org.nodes
        );
      }
      setChecking(false);
    }
    checkOrg();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (checking) {
    return (
      <div className="boot-screen">
        <div className="boot-logo">◈ OPENTHRALL</div>
        <div className="boot-status">CHECKING KERNEL…</div>
      </div>
    );
  }

  if (!store.bootstrapped) {
    return <BootstrapWizard onComplete={() => {}} />;
  }

  return <AppShell />;
}

export default function App() {
  return (
    <AppStoreProvider>
      <AppInner />
    </AppStoreProvider>
  );
}
