import { useEffect, useState } from "react";
import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { api } from "../api/client";
import type { ThresholdMeta, Thresholds } from "../types";

interface Props {
  // The thresholds currently applied to the dataset (from the analyze response).
  applied: Thresholds;
  busy: boolean;
  onApply: (next: Thresholds) => void;
}

// Rate fields are stored as fractions (0.05) but shown/edited as percent (5).
export function ThresholdsPanel({ applied, busy, onApply }: Props) {
  const [open, setOpen] = useState(false);
  const [meta, setMeta] = useState<Record<string, ThresholdMeta>>({});
  const [defaults, setDefaults] = useState<Thresholds>({});
  const [draft, setDraft] = useState<Thresholds>(applied);

  useEffect(() => {
    api
      .thresholdConfig()
      .then((c) => {
        setMeta(c.meta);
        setDefaults(c.defaults);
      })
      .catch(() => {
        /* non-fatal: panel just won't render fields */
      });
  }, []);

  // Keep the draft in sync when the applied thresholds change (e.g. new dataset).
  useEffect(() => setDraft(applied), [applied]);

  const keys = Object.keys(meta);
  if (keys.length === 0) return null;

  const dirty = keys.some((k) => draft[k] !== applied[k]);

  function setField(key: string, kind: ThresholdMeta["kind"], raw: string) {
    const n = Number(raw);
    if (Number.isNaN(n)) return;
    const value = kind === "rate" ? n / 100 : Math.round(n);
    setDraft((d) => ({ ...d, [key]: value }));
  }

  return (
    <div className="rounded-xl border border-line bg-ink-700 shadow-panel">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-semibold text-content"
      >
        <SlidersHorizontal className="h-4 w-4 text-brand-400" />
        Detection thresholds
        <span className="text-xs font-normal text-content-faint">
          {open ? "— tune the rules and re-run" : "— adjust what counts as a problem"}
        </span>
        <span className="ml-auto text-xs text-content-faint">{open ? "Hide" : "Edit"}</span>
      </button>

      {open && (
        <div className="border-t border-line p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {keys.map((k) => {
              const m = meta[k];
              const isRate = m.kind === "rate";
              const shown = isRate ? +(draft[k] * 100).toFixed(2) : draft[k];
              return (
                <label key={k} className="flex flex-col gap-1 text-xs text-content-muted">
                  <span>{m.label}</span>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={shown}
                      min={0}
                      step={isRate ? 0.5 : 1}
                      onChange={(e) => setField(k, m.kind, e.target.value)}
                      className="w-full rounded-md border border-line-strong bg-ink-600 px-2 py-1 text-sm text-content focus:border-brand-500 focus:outline-none"
                    />
                    <span className="text-content-faint">{isRate ? "%" : "#"}</span>
                  </div>
                </label>
              );
            })}
          </div>

          <div className="mt-4 flex items-center gap-2">
            <button
              onClick={() => onApply(draft)}
              disabled={!dirty || busy}
              className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
            >
              {busy ? "Applying…" : "Apply & re-run"}
            </button>
            <button
              onClick={() => setDraft(defaults)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-sm text-content-muted transition-colors hover:text-content disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Reset to defaults
            </button>
            {dirty && <span className="text-xs text-amber-300">Unsaved changes</span>}
          </div>
        </div>
      )}
    </div>
  );
}
