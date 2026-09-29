import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { CampaignMetrics } from "../types";
import { num, pct } from "../lib/format";

type SortKey = keyof Pick<
  CampaignMetrics,
  "campaign_name" | "sent" | "bounced" | "replies" | "bounce_rate" | "reply_rate"
>;

export function CampaignTable({ campaigns }: { campaigns: CampaignMetrics[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("sent");
  const [asc, setAsc] = useState(false);

  const sorted = useMemo(() => {
    const copy = [...campaigns];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return asc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return copy;
  }, [campaigns, sortKey, asc]);

  function toggle(key: SortKey) {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(false);
    }
  }

  const Th = ({ k, label, right }: { k: SortKey; label: string; right?: boolean }) => (
    <th
      onClick={() => toggle(k)}
      className={`cursor-pointer select-none px-3 py-2 font-medium text-content-muted transition-colors hover:text-content ${
        right ? "text-right" : "text-left"
      }`}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortKey === k && (asc ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </span>
    </th>
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-ink-700 shadow-panel">
      <table className="min-w-full text-sm">
        <thead className="border-b border-line bg-ink-600 text-xs uppercase tracking-wide">
          <tr>
            <Th k="campaign_name" label="Campaign" />
            <th className="px-3 py-2 text-left font-medium text-content-muted">Domain</th>
            <Th k="sent" label="Sent" right />
            <Th k="bounced" label="Bounced" right />
            <Th k="replies" label="Replies" right />
            <Th k="bounce_rate" label="Bounce %" right />
            <Th k="reply_rate" label="Reply %" right />
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => (
            <tr key={c.campaign_name} className="border-b border-line/60 last:border-0 transition-colors hover:bg-ink-600/60">
              <td className="px-3 py-2 font-medium text-content">{c.campaign_name}</td>
              <td className="px-3 py-2 text-content-muted">{c.domain || "—"}</td>
              <td className="px-3 py-2 text-right tabular-nums text-content-muted">{num(c.sent)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-content-muted">{num(c.bounced)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-content-muted">{num(c.replies)}</td>
              <td className={`px-3 py-2 text-right tabular-nums ${c.bounce_rate >= 0.05 ? "font-medium text-red-400" : "text-content-muted"}`}>
                {pct(c.bounce_rate)}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-content-muted">
                {pct(c.reply_rate)}
                <span className="ml-1 text-[10px] text-content-faint">/{c.reply_rate_denominator}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
