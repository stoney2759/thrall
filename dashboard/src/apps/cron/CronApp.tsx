import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
interface Props { activeView: string; }
export function CronApp({ activeView }: Props) {
  return <PlaceholderView app="Cron" view={activeView} />;
}
