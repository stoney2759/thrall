import React from "react";
import { ThrallChatPanel } from "../../components/ThrallChatPanel";
import { PlaceholderView } from "../../components/PlaceholderView";

interface Props { activeView: string; }

export function ChatApp({ activeView }: Props) {
  switch (activeView) {
    case "sessions":  return <ThrallChatPanel />;
    case "channels":  return <PlaceholderView app="Chat" view="Channels" message="Multi-channel routing coming soon." />;
    case "instances": return <PlaceholderView app="Chat" view="Instances" message="Instance management coming soon." />;
    default:          return <ThrallChatPanel />;
  }
}
