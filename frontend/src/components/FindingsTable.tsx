import { Fragment, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { Finding, FindingStatus, Severity } from "../types";
import { categoryLabels, severityStyles, statusStyles } from "../lib/format";

const SEVERITIES: Severity[] = ["high", "medium", "low", "info"];
const STATUSES: FindingStatus[] = ["Open", "Investigating", "Resolved", "Dismissed"];

interface Props {
  findings: Finding[];
  insufficientNotes: string[];
  onStatusChange: (findingId: string, status: FindingStatus) => void;
}

export function FindingsTable({ findings, insufficientNotes, onStatusChange }: Props) {
  const [severity, setSeverity] = useState<Severity | "">("");
  const [status, setStatus] = useState<FindingStatus | "">("");
  const [campaign, setCampaign] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const campaigns = useMemo(
    () => Array.from(new Set(findings.map((f) => f.campaign_name).filter(Boolean))) as string[],
    [findings],
  );

  const filtered = useMemo(
    () =>
      findings.filter(
        (f) =>
          (!severity || f.severity === severity) &&
          (!status || f.status === status) &&
          (!campaign || f.campaign_name === campaign),
      ),
    [findings, severity, status, campaign],
  );

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const selectCls =
    "rounded-md border border-line-strong bg-ink-600 px-2 py-1 text-sm text-content focus:border-brand-500 focus:outline-none";

  return (
    <div className="rounded-xl border border-line bg-ink-700 shadow-panel">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
        <h3 className="mr-auto text-sm font-semibold text-content">
          Findings <span className="text-content-faint">({filtered.length})</span>
        </h3>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as Severity | "")}
          className={selectCls}
          aria-label="Filter by severity"
        >
          <option value="">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as FindingStatus | "")}
          className={selectCls}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={campaign}
          onChange={(e) => setCampaign(e.target.value)}
          className={selectCls}
          aria-label="Filter by campaign"
        >
          <option value="">All campaigns</option>
          {campaigns.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className="p-8 text-center text-sm text-content-muted">
          No findings match the current filters.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="border-b border-line bg-ink-600 text-xs uppercase tracking-wide text-content-muted">
              <tr>
                <th className="w-8 px-3 py-2" />
                <th className="px-3 py-2 text-left font-medium">Severity</th>
                <th className="px-3 py-2 text-left font-medium">Finding</th>
                <th className="px-3 py-2 text-left font-medium">Campaign</th>
                <th className="px-3 py-2 text-left font-medium">Confidence</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => {
                const isOpen = expanded.has(f.id);
                return (
                  <Fragment key={f.id}>
                    <tr className="border-b border-line/60 transition-colors hover:bg-ink-600/60">
                      <td className="px-3 py-2 align-top">
                        <button onClick={() => toggle(f.id)} aria-label="Toggle details">
                          {isOpen ? (
                            <ChevronDown className="h-4 w-4 text-content-faint" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-content-faint" />
                          )}
                        </button>
                      </td>
                      <td className="px-3 py-2 align-top">
                        <span
                          className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold uppercase ${severityStyles[f.severity]}`}
                        >
                          {f.severity}
                        </span>
                      </td>
                      <td className="px-3 py-2 align-top">
                        <div className="font-medium text-content">{f.title}</div>
                        <div className="text-xs text-content-muted">
                          {categoryLabels[f.category] ?? f.category} · {f.evidence}
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-content-muted">
                        {f.campaign_name || "—"}
                        {f.domain && <div className="text-xs text-content-faint">{f.domain}</div>}
                      </td>
                      <td className="px-3 py-2 align-top capitalize text-content-muted">{f.confidence}</td>
                      <td className="px-3 py-2 align-top">
                        <select
                          value={f.status}
                          onChange={(e) => onStatusChange(f.id, e.target.value as FindingStatus)}
                          className={`rounded px-2 py-1 text-xs font-medium ${statusStyles[f.status]}`}
                          aria-label={`Status for ${f.title}`}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="border-b border-line/60 bg-ink-800/60">
                        <td />
                        <td colSpan={5} className="px-3 py-3">
                          <FindingDetail finding={f} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {insufficientNotes.length > 0 && (
        <div className="border-t border-line bg-amber-500/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-300">
            Data-quality notes ({insufficientNotes.length})
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-amber-200/80">
            {insufficientNotes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function FindingDetail({ finding: f }: { finding: Finding }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div>
        <p className="text-sm text-content-muted">{f.explanation}</p>
        {f.comparison && (
          <div className="mt-2 rounded-md bg-ink-600 p-2 text-xs text-content-muted ring-1 ring-line-strong">
            <span className="font-medium text-content">{f.comparison.label}</span>: prior{" "}
            {(f.comparison.prior_value! * 100).toFixed(1)}% ({f.comparison.prior_period}) → current{" "}
            {(f.comparison.current_value! * 100).toFixed(1)}% ({f.comparison.current_period})
          </div>
        )}
        {f.threshold_used && (
          <p className="mt-2 text-xs text-content-faint">
            <span className="font-medium text-content-muted">Threshold:</span> {f.threshold_used}
          </p>
        )}
        {f.data_limitations && (
          <p className="mt-1 text-xs text-amber-300/90">
            <span className="font-medium">Limitations:</span> {f.data_limitations}
          </p>
        )}
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-content-faint">
          Recommended checks
        </p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-content-muted">
          {f.recommendations.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
