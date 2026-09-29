# Architecture

Campaign Ops Copilot is a two-tier app: a React SPA talks to a FastAPI backend
over a small JSON API. All analysis is rule-based and runs server-side; no
external services are contacted and no data is persisted to disk.

```
React + TS + Vite  ──  /api (JSON, proxied by Vite in dev)  ──▶  FastAPI (Uvicorn)

  UploadPanel / Demo        POST /upload, POST /demo             api/routes.py  (transport)
  KPI cards                 GET  /datasets/{id}/summary                 │
  Recharts (trend/compare)  GET  /datasets/{id}/campaigns               ▼
  Campaign table            POST /datasets/{id}/analyze          analysis/  (pure engine)
  Findings table + filters  GET  /datasets/{id}/findings          validation → metrics
  Export buttons            GET  /datasets/{id}/report            → anomalies → recommendations → reports
                                                                 store.py  (in-memory)
                                                                 config.py (thresholds/policy)
```

## Backend layering

The backend is deliberately layered so business logic is decoupled from
transport and storage — this is what makes the app cheap to evolve.

1. **`api/routes.py` (transport).** Thin. Parses HTTP input, calls the engine,
   serializes Pydantic models. No metric math lives here.
2. **`analysis/` (engine).** Pure functions over a validated pandas DataFrame:
   - `validation.py` — parse + validate untrusted CSV → clean DataFrame + report.
   - `metrics.py` — zero-safe metric calculations with documented denominators.
   - `anomalies.py` — deterministic rules → findings + insufficient-data notes.
   - `recommendations.py` — maps a finding category → investigation steps.
   - `reports.py` — CSV + print-friendly HTML export.
   None of these import FastAPI or the store; they can be unit-tested in isolation.
3. **`store.py` (storage).** In-memory, thread-safe, opaque UUID keys. The only
   stateful component. Swapping it for a database later touches this file plus a
   few route calls — the engine is untouched.
4. **`config.py` (policy).** All thresholds and limits in one place so rules stay
   configurable and every finding can cite its threshold.

## Request flow (typical)

1. Client `POST /api/upload` (or `/api/demo`).
2. `validation.parse_and_validate` cleans the CSV; the store returns an opaque
   `dataset_id`; `metrics.compute_summary` produces immediate KPIs.
3. Client `POST /api/datasets/{id}/analyze` runs `anomalies.detect`; findings are
   cached on the dataset record.
4. Client fetches `/summary`, `/campaigns`, `/findings` (findings support
   filters); analysis runs lazily if `/summary` or `/findings` is hit first.
5. `/report` renders CSV or HTML from cached findings + recomputed metrics.

## Frontend structure

- `api/client.ts` — the single typed gateway to the backend (`ApiError` for
  structured failures).
- `types.ts` — TypeScript mirror of the backend Pydantic models.
- `App.tsx` — orchestrates dataset lifecycle and loading/error/empty states.
- `components/` — presentational units (KPI cards, charts, tables, upload panel,
  shared state components).

## Design decisions & tradeoffs

- **Rule-based, not ML/LLM.** Deterministic, explainable, zero-cost, and easy to
  test. The recommendation layer is a clean seam where optional LLM-generated
  summaries could be added later without touching the metric math.
- **In-memory storage.** Right-sized for an MVP/demo; limitations are documented
  rather than hidden. Single-worker deployment recommended.
- **Insufficient data is a first-class outcome.** Comparisons require a volume
  floor; otherwise the tool reports the gap instead of inventing a trend.
- **Pandas in the request path.** Fine within the enforced file-size/row limits;
  a background worker would be the next step for very large files.

## Scaling path (not built in the MVP)

1. Replace `store.py` with Postgres/Redis for persistence + multi-worker support.
2. Move heavy analysis to a task queue (e.g. RQ/Celery) for large uploads.
3. Add the optional LLM summary behind the existing recommendation seam.
4. Add authenticated, authorized platform integrations.

These are intentionally out of scope until the core MVP is solid.
