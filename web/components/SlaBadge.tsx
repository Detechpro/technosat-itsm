import type { SlaState } from "@/lib/types";
import { t as dict, type Lang } from "@/lib/i18n";

/** Shows one SLA clock state with a colour. */
export function SlaBadge({ state, lang }: { state?: SlaState; lang: Lang }) {
  const ui = dict(lang);
  const label = state === "met" ? ui.slaMet
    : state === "breached" ? ui.slaBreached
    : state === "running" ? ui.slaRunning
    : state === "stopped" ? ui.slaStopped
    : "—";
  return <span className={`badge sla-${state ?? "none"}`}>{label}</span>;
}
