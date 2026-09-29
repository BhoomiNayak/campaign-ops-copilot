import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CampaignMetrics, TrendPoint } from "../types";
import { pct } from "../lib/format";

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-ink-700 p-4 shadow-panel">
      <h3 className="text-sm font-semibold text-content">{title}</h3>
      {subtitle && <p className="mb-2 text-xs text-content-faint">{subtitle}</p>}
      <div className="h-64 w-full">{children}</div>
    </div>
  );
}

const pctTick = (v: number) => `${(v * 100).toFixed(0)}%`;
const pctTip = (v: number) => pct(v);

// Shared dark styling for Recharts primitives.
const GRID = "#1e2836";
const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" };
const tooltipStyle = {
  contentStyle: {
    background: "#131a25",
    border: "1px solid #2b3849",
    borderRadius: 8,
    color: "#e6edf6",
  },
  labelStyle: { color: "#94a3b8" },
  itemStyle: { color: "#e6edf6" },
};

export function TrendChart({ trend }: { trend: TrendPoint[] }) {
  return (
    <ChartCard title="Bounce & reply rate over time" subtitle="Daily, across all campaigns">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={trend} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="date" tick={AXIS_TICK} stroke={GRID} tickFormatter={(d: string) => d.slice(5)} />
          <YAxis tick={AXIS_TICK} stroke={GRID} tickFormatter={pctTick} />
          <Tooltip formatter={(v: number) => pctTip(v)} {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
          <Line type="monotone" dataKey="bounce_rate" name="Bounce rate" stroke="#f87171" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="reply_rate" name="Reply rate" stroke="#38bdf8" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function CampaignComparisonChart({ campaigns }: { campaigns: CampaignMetrics[] }) {
  // Show the top campaigns by volume to keep the chart readable.
  const data = campaigns.slice(0, 8).map((c) => ({
    name: c.campaign_name.length > 16 ? c.campaign_name.slice(0, 15) + "…" : c.campaign_name,
    bounce_rate: c.bounce_rate,
    reply_rate: c.reply_rate,
  }));

  return (
    <ChartCard title="Campaign comparison" subtitle="Bounce vs. reply rate by campaign">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} stroke={GRID} interval={0} angle={-12} textAnchor="end" height={48} />
          <YAxis tick={AXIS_TICK} stroke={GRID} tickFormatter={pctTick} />
          <Tooltip formatter={(v: number) => pctTip(v)} cursor={{ fill: "rgba(108,99,255,0.08)" }} {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
          <Bar dataKey="bounce_rate" name="Bounce rate" fill="#f87171" radius={[3, 3, 0, 0]} />
          <Bar dataKey="reply_rate" name="Reply rate" fill="#38bdf8" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
