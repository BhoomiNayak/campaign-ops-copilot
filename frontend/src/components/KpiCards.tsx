import {
  Mail,
  MailWarning,
  MessageSquareReply,
  Megaphone,
  AlertCircle,
  Percent,
} from "lucide-react";
import type { DatasetSummary } from "../types";
import { num, pct } from "../lib/format";

function Card({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-ink-700 p-4 shadow-panel transition-colors hover:border-line-strong">
      <div className="flex items-center justify-between">
        <span className="text-sm text-content-muted">{label}</span>
        <span className="text-brand-400/80">{icon}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-content">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-content-faint">{sub}</div>}
    </div>
  );
}

export function KpiCards({ summary }: { summary: DatasetSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Card icon={<Mail className="h-4 w-4" />} label="Total sent" value={num(summary.total_sent)} />
      <Card
        icon={<MailWarning className="h-4 w-4" />}
        label="Total bounced"
        value={num(summary.total_bounced)}
      />
      <Card
        icon={<Percent className="h-4 w-4" />}
        label="Bounce rate"
        value={pct(summary.bounce_rate)}
        sub="bounced / sent"
      />
      <Card
        icon={<MessageSquareReply className="h-4 w-4" />}
        label="Reply rate"
        value={pct(summary.reply_rate)}
        sub={`replies / ${summary.reply_rate_denominator}`}
      />
      <Card
        icon={<Megaphone className="h-4 w-4" />}
        label="Campaigns"
        value={num(summary.num_campaigns)}
      />
      <Card
        icon={<AlertCircle className="h-4 w-4" />}
        label="Findings"
        value={num(summary.num_findings)}
      />
    </div>
  );
}
