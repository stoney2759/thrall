// ============================================================
// AppShell.tsx — Root layout shell
// Composes: LeftRail | TopToolbar | ContentArea
// ============================================================

import React from "react";
import { LeftRail } from "./LeftRail";
import { TopToolbar } from "./TopToolbar";
import { ContentArea } from "./ContentArea";

export function AppShell() {
  return (
    <div className="app-shell">
      <LeftRail />
      <div className="shell-right">
        <TopToolbar />
        <ContentArea />
      </div>
    </div>
  );
}
