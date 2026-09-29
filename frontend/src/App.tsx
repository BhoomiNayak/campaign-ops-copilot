import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Activity, Download, FileText, RefreshCw } from "lucide-react";
import { api, ApiError } from "./api/client";
import type {
  CampaignsResponse,
  DatasetSummary,
  Finding,
  FindingStatus,
  UploadResponse,
} from "./types";
import { UploadPanel } from "./components/UploadPanel";
import { KpiCards } from "./components/KpiCards";
import { CampaignTable } from "./components/CampaignTable";
import { FindingsTable } from "./components/FindingsTable";
import { ThresholdsPanel } from "./components/ThresholdsPanel";
import { EmptyState, ErrorState, LoadingState } from "./components/States";
import type { Thresholds } from "./types";

// Code-split the charts so Recharts is only fetched once a dataset is loaded.
const ChartsSection = lazy(() => import("./components/ChartsSection"));

export default function App() {
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [campaigns, setCampaigns] = useState<CampaignsResponse | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [thresholds, setThresholds] = useState<Thresholds>({});
  const [applying, setApplying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDataset = useCallback(async (id: string, override?: Thresholds) => {
    setLoading(true);
    setError(null);
    try {
      // Run analysis (optionally with tuned thresholds), then fetch
      // summary + campaigns in parallel.
      const analysis = await api.analyze(id, override);
      const [sum, camp] = await Promise.all([api.summary(id), api.campaigns(id)]);
      setSummary(sum);
      setCampaigns(camp);
      setFindings(analysis.findings);
      setNotes(analysis.insufficient_data_notes);
      setThresholds(analysis.thresholds);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load analysis.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function handleApplyThresholds(next: Thresholds) {
    if (!datasetId) return;
    setApplying(true);
    try {
      await loadDataset(datasetId, next);
    } finally {
      setApplying(false);
    }
  }

  function handleLoaded(res: UploadResponse) {
    if (!res.dataset_id) return;
    setDatasetId(res.dataset_id);
    // Store the summary immediately for a snappy UI; full analysis follows.
    if (res.summary) setSummary(res.summary);
    void loadDataset(res.dataset_id);
  }

  async function handleStatusChange(findingId: string, status: FindingStatus) {
    if (!datasetId) return;
    // Optimistic update.
    setFindings((prev) => prev.map((f) => (f.id === findingId ? { ...f, status } : f)));
    try {
      await api.setFindingStatus(datasetId, findingId, status);
    } catch {
      // Revert on failure by reloading findings.
      if (datasetId) {
        const fresh = await api.findings(datasetId);
        setFindings(fresh.findings);
      }
    }
  }

  useEffect(() => {
    // Best-effort health ping to surface a down backend early.
    api.health().catch(() =>
      setError("Cannot reach the backend at /api. Is the FastAPI server running on port 8000?"),
    );
  }, []);

  const hasData = datasetId && summary;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-ink-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-glow">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-content">
              Campaign Ops <span className="text-brand-400">Copilot</span>
            </h1>
            <p className="text-xs text-content-faint">
              Rule-based campaign analytics · surfaces issues worth investigating
            </p>
          </div>
          {hasData && (
            <div className="ml-auto flex items-center gap-2">
              <a
                href={api.reportUrl(datasetId!, "summary_csv")}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-sm text-content-muted transition-colors hover:border-brand-500 hover:text-content"
              >
                <Download className="h-4 w-4" /> Summary CSV
              </a>
              <a
                href={api.reportUrl(datasetId!, "findings_csv")}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-sm text-content-muted transition-colors hover:border-brand-500 hover:text-content"
              >
                <Download className="h-4 w-4" /> Findings CSV
              </a>
              <a
                href={api.reportUrl(datasetId!, "html")}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-600"
              >
                <FileText className="h-4 w-4" /> Report
              </a>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6">
        <UploadPanel onLoaded={handleLoaded} />

        {error && <ErrorState message={error} onRetry={datasetId ? () => loadDataset(datasetId) : undefined} />}

        {loading && <LoadingState label="Analyzing campaigns…" />}

        {!loading && !error && !hasData && (
          <EmptyState
            title="No dataset loaded yet"
            hint="Upload a CSV or click “Try demo data” to explore the dashboard."
          />
        )}

        {!loading && hasData && summary && campaigns && (
          <>
            <section>
              <KpiCards summary={summary} />
            </section>

            <Suspense fallback={<LoadingState label="Loading charts…" />}>
              <ChartsSection trend={campaigns.trend} campaigns={campaigns.campaigns} />
            </Suspense>

            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-content">Campaigns</h2>
                <button
                  onClick={() => datasetId && loadDataset(datasetId)}
                  className="inline-flex items-center gap-1.5 text-sm text-content-muted transition-colors hover:text-content"
                >
                  <RefreshCw className="h-4 w-4" /> Refresh
                </button>
              </div>
              <CampaignTable campaigns={campaigns.campaigns} />
            </section>

            <section className="space-y-4">
              <ThresholdsPanel
                applied={thresholds}
                busy={applying}
                onApply={handleApplyThresholds}
              />
              <FindingsTable
                findings={findings}
                insufficientNotes={notes}
                onStatusChange={handleStatusChange}
              />
            </section>
          </>
        )}
      </main>

      <footer className="border-t border-line py-6 text-center text-xs text-content-faint">
        In-memory MVP · data is not persisted and never leaves this server · demo data is synthetic
      </footer>
    </div>
  );
}
