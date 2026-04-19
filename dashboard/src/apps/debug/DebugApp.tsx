import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function DebugApp({ activeView }: Props) {
  return <PlaceholderView app="Debug" view={activeView} />;
}
