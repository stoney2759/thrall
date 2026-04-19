import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function DocsApp({ activeView }: Props) {
  return <PlaceholderView app="Docs" view={activeView} />;
}
