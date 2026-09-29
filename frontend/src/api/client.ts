// Typed API client. All requests go to /api and are proxied to the FastAPI
// backend by Vite during development (see vite.config.ts).

import type {
  AnalyzeResponse,
  CampaignsResponse,
  DatasetSummary,
  Finding,
  FindingFilters,
  FindingStatus,
  ThresholdConfigResponse,
  Thresholds,
  UploadResponse,
} from "../types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function parseError(res: Response): Promise<never> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    /* non-JSON error body */
  }
  throw new ApiError(res.status, detail);
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) await parseError(res);
  return res.json() as Promise<T>;
}

export const api = {
  async health(): Promise<{ status: string; version: string }> {
    return getJson(`${BASE}/health`);
  },

  async uploadCsv(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
    if (!res.ok) await parseError(res);
    return res.json() as Promise<UploadResponse>;
  },

  async loadDemo(): Promise<UploadResponse> {
    const res = await fetch(`${BASE}/demo`, { method: "POST" });
    if (!res.ok) await parseError(res);
    return res.json() as Promise<UploadResponse>;
  },

  async summary(datasetId: string): Promise<DatasetSummary> {
    return getJson(`${BASE}/datasets/${datasetId}/summary`);
  },

  async campaigns(datasetId: string): Promise<CampaignsResponse> {
    return getJson(`${BASE}/datasets/${datasetId}/campaigns`);
  },

  async analyze(datasetId: string, thresholds?: Thresholds | null): Promise<AnalyzeResponse> {
    const res = await fetch(`${BASE}/datasets/${datasetId}/analyze`, {
      method: "POST",
      headers: thresholds ? { "Content-Type": "application/json" } : undefined,
      body: thresholds ? JSON.stringify({ thresholds }) : undefined,
    });
    if (!res.ok) await parseError(res);
    return res.json() as Promise<AnalyzeResponse>;
  },

  async thresholdConfig(): Promise<ThresholdConfigResponse> {
    return getJson(`${BASE}/config/thresholds`);
  },

  async findings(datasetId: string, filters: FindingFilters = {}): Promise<AnalyzeResponse> {
    const params = new URLSearchParams();
    if (filters.severity) params.set("severity", filters.severity);
    if (filters.campaign) params.set("campaign", filters.campaign);
    if (filters.domain) params.set("domain", filters.domain);
    if (filters.status) params.set("status", filters.status);
    const qs = params.toString();
    return getJson(`${BASE}/datasets/${datasetId}/findings${qs ? `?${qs}` : ""}`);
  },

  async setFindingStatus(
    datasetId: string,
    findingId: string,
    status: FindingStatus,
  ): Promise<Finding> {
    const res = await fetch(
      `${BASE}/datasets/${datasetId}/findings/${findingId}?status=${encodeURIComponent(status)}`,
      { method: "PATCH" },
    );
    if (!res.ok) await parseError(res);
    return res.json() as Promise<Finding>;
  },

  reportUrl(datasetId: string, format: "html" | "summary_csv" | "findings_csv"): string {
    return `${BASE}/datasets/${datasetId}/report?format=${format}`;
  },

  sampleCsvUrl(): string {
    return `${BASE}/sample.csv`;
  },
};
