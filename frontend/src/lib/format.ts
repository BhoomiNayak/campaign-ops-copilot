// Small formatting helpers shared across components.

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number): string {
  return value.toLocaleString();
}

export const severityStyles: Record<string, string> = {
  high: "bg-red-500/15 text-red-300 border-red-500/30",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  low: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  info: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

export const statusStyles: Record<string, string> = {
  Open: "bg-ink-500 text-content-muted",
  Investigating: "bg-amber-500/20 text-amber-300",
  Resolved: "bg-emerald-500/20 text-emerald-300",
  Dismissed: "bg-ink-600 text-content-faint line-through",
};

export const categoryLabels: Record<string, string> = {
  elevated_bounce: "Elevated bounce",
  bounce_spike: "Bounce spike",
  declining_replies: "Declining replies",
  low_replies: "Low replies",
  repeated_issue: "Repeated issue",
  incomplete_data: "Incomplete data",
};
