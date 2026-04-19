// ============================================================
// PlaceholderView.tsx — Consistent placeholder for future views
// ============================================================

import React from "react";

interface PlaceholderViewProps {
  app: string;
  view?: string;
  message?: string;
}

export function PlaceholderView({ app, view, message }: PlaceholderViewProps) {
  return (
    <div className="placeholder-view">
      <div className="placeholder-inner">
        <div className="placeholder-tag">COMING SOON</div>
        <h2 className="placeholder-title">
          {app}{view ? ` · ${view}` : ""}
        </h2>
        <p className="placeholder-msg">
          {message ?? "This module is not yet implemented. Structure and routing are in place."}
        </p>
        <div className="placeholder-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="placeholder-cell" style={{ opacity: 1 - i * 0.12 }} />
          ))}
        </div>
      </div>
    </div>
  );
}
