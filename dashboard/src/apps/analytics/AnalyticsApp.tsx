import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function AnalyticsApp({ activeView }: Props) {
  return <PlaceholderView app="Analytics" view={activeView} />;
}
