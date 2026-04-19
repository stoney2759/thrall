import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function LlmApp({ activeView }: Props) {
  return <PlaceholderView app="LLM" view={activeView} />;
}
