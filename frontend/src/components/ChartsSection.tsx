// Default-exported wrapper so the charts (and the heavy Recharts dependency)
// can be code-split via React.lazy in App.tsx (audit L6). Keeping this as its
// own module means Recharts lands in a separate chunk loaded only once a
// dataset is present, shrinking the initial bundle.

import type { CampaignMetrics, TrendPoint } from "../types";
import { CampaignComparisonChart, TrendChart } from "./Charts";

interface Props {
  trend: TrendPoint[];
  campaigns: CampaignMetrics[];
}

export default function ChartsSection({ trend, campaigns }: Props) {
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <TrendChart trend={trend} />
      <CampaignComparisonChart campaigns={campaigns} />
    </section>
  );
}
