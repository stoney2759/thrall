import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function MemoryApp({ activeView }: Props) {
  return <PlaceholderView app="Memory" view={activeView} />;
}
