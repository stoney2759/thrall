import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function SandboxApp({ activeView }: Props) {
  return <PlaceholderView app="Sandbox" view={activeView} />;
}
