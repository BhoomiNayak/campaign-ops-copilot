import { useRef, useState } from "react";
import { Download, FileUp, Play, Loader2 } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { UploadResponse, ValidationReport } from "../types";

interface Props {
  onLoaded: (res: UploadResponse) => void;
}

export function UploadPanel({ onLoaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);

  async function handleFile(file: File) {
    setError(null);
    setValidation(null);
    setBusy("upload");
    try {
      const res = await api.uploadCsv(file);
      if (!res.summary || !res.dataset_id) {
        // File-level validation failed — surface the report, do not proceed.
        setValidation(res.validation);
        return;
      }
      if (res.validation.warnings.length > 0) setValidation(res.validation);
      onLoaded(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDemo() {
    setError(null);
    setValidation(null);
    setBusy("demo");
    try {
      const res = await api.loadDemo();
      onLoaded(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load demo data.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-ink-700 p-6 shadow-panel">
      <div className="pointer-events-none absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-brand-500/60 to-transparent" />
      <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-lg">
          <h2 className="text-lg font-semibold text-content">Load campaign data</h2>
          <p className="mt-1 text-sm text-content-muted">
            Upload a CSV with columns <code className="rounded bg-ink-500 px-1 text-content">date</code>,{" "}
            <code className="rounded bg-ink-500 px-1 text-content">campaign_name</code>,{" "}
            <code className="rounded bg-ink-500 px-1 text-content">sent</code>,{" "}
            <code className="rounded bg-ink-500 px-1 text-content">bounced</code>,{" "}
            <code className="rounded bg-ink-500 px-1 text-content">replies</code>. Optional:{" "}
            <code className="rounded bg-ink-500 px-1 text-content">domain, mailbox, delivered, opens, clicks</code>.
          </p>
          <p className="mt-2 text-xs text-content-faint">
            Your data is processed in memory only and never sent to third-party services.
          </p>
        </div>

        <div className="flex shrink-0 flex-col gap-2 sm:flex-row md:flex-col">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => inputRef.current?.click()}
            disabled={busy !== null}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white shadow-glow transition-colors hover:bg-brand-600 disabled:opacity-60"
          >
            {busy === "upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
            Upload CSV
          </button>
          <button
            onClick={handleDemo}
            disabled={busy !== null}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-line-strong bg-ink-600 px-4 py-2 text-sm font-medium text-content transition-colors hover:border-brand-500 disabled:opacity-60"
          >
            {busy === "demo" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Try demo data
          </button>
          <a
            href={api.sampleCsvUrl()}
            className="inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-brand-400 hover:text-brand-500 hover:underline"
          >
            <Download className="h-4 w-4" />
            Sample CSV
          </a>
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {validation && !validation.ok && (
        <ValidationErrors report={validation} />
      )}
      {validation && validation.ok && validation.warnings.length > 0 && (
        <ValidationWarnings report={validation} />
      )}
    </div>
  );
}

function ValidationErrors({ report }: { report: ValidationReport }) {
  return (
    <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
      <p className="text-sm font-semibold text-red-300">
        Validation failed — {report.errors.length} issue(s). No dataset was created.
      </p>
      {report.missing_required_columns.length > 0 && (
        <p className="mt-1 text-sm text-red-300/90">
          Missing required columns: {report.missing_required_columns.join(", ")}. Expected:{" "}
          date, campaign_name, sent, bounced, replies.
        </p>
      )}
      <ul className="mt-2 max-h-48 space-y-1 overflow-auto text-xs text-red-300/80">
        {report.errors.slice(0, 50).map((e, i) => (
          <li key={i}>
            {e.row ? `Row ${e.row}: ` : ""}
            {e.column ? `[${e.column}] ` : ""}
            {e.message}
          </li>
        ))}
      </ul>
      {report.warnings.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-red-500/20 pt-2 text-xs text-red-300/70">
          {report.warnings.slice(0, 20).map((w, i) => (
            <li key={i}>{w.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ValidationWarnings({ report }: { report: ValidationReport }) {
  return (
    <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
      <p className="text-sm font-semibold text-amber-300">
        Loaded {report.valid_rows} of {report.total_rows} rows with {report.warnings.length} warning(s).
      </p>
      <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-xs text-amber-300/80">
        {report.warnings.slice(0, 30).map((w, i) => (
          <li key={i}>
            {w.row ? `Row ${w.row}: ` : ""}
            {w.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
