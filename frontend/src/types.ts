// Shared types mirroring the backend Pydantic models (app/models.py).
// Kept in sync manually; the backend OpenAPI schema at /openapi.json is the
// source of truth if these ever drift.

export type Severity = "info" | "low" | "medium" | "high";

export type FindingCategory =
  | "elevated_bounce"
  | "bounce_spike"
  | "declining_replies"
  | "low_replies"
  | "repeated_issue"
  | "incomplete_data";

export type FindingStatus = "Open" | "Investigating" | "Resolved" | "Dismissed";

export type Confidence = "low" | "medium" | "high";

export interface ValidationIssue {
  row?: number | null;
  column?: string | null;
  code: string;
  message: string;
}

export interface ValidationReport {
  ok: boolean;
  total_rows: number;
  valid_rows: number;
  dropped_rows: number;
  duplicate_rows: number;
  detected_columns: string[];
  missing_required_columns: string[];
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface MetricNote {
  metric: string;
  definition: string;
  denominator_used?: string | null;
}

export interface DatasetSummary {
  dataset_id: string;
  period_start?: string | null;
  period_end?: string | null;
  total_sent: number;
  total_bounced: number;
  total_replies: number;
  total_delivered?: number | null;
  bounce_rate: number;
  reply_rate: number;
  reply_rate_denominator: string;
  num_campaigns: number;
  num_findings: number;
  notes: MetricNote[];
}

export interface CampaignMetrics {
  campaign_name: string;
  domain?: string | null;
  sent: number;
  bounced: number;
  replies: number;
  delivered?: number | null;
  bounce_rate: number;
  reply_rate: number;
  reply_rate_denominator: string;
  periods: number;
}

export interface TrendPoint {
  date: string;
  sent: number;
  bounced: number;
  replies: number;
  bounce_rate: number;
  reply_rate: number;
}

export interface CampaignsResponse {
  dataset_id: string;
  campaigns: CampaignMetrics[];
  trend: TrendPoint[];
}

export interface PeriodComparison {
  label: string;
  current_value?: number | null;
  prior_value?: number | null;
  current_period?: string | null;
  prior_period?: string | null;
}

export interface Finding {
  id: string;
  campaign_name?: string | null;
  domain?: string | null;
  severity: Severity;
  category: FindingCategory;
  title: string;
  metric: string;
  evidence: string;
  explanation: string;
  recommendations: string[];
  comparison?: PeriodComparison | null;
  confidence: Confidence;
  data_limitations?: string | null;
  threshold_used?: string | null;
  status: FindingStatus;
}

export interface AnalyzeResponse {
  dataset_id: string;
  findings: Finding[];
  thresholds: Record<string, number>;
  insufficient_data_notes: string[];
}

export interface UploadResponse {
  dataset_id: string;
  validation: ValidationReport;
  summary?: DatasetSummary | null;
}

export interface FindingFilters {
  severity?: Severity;
  campaign?: string;
  domain?: string;
  status?: FindingStatus;
}

// Anomaly thresholds are a flat map of name -> number.
export type Thresholds = Record<string, number>;

export interface ThresholdMeta {
  label: string;
  kind: "rate" | "count";
}

export interface ThresholdConfigResponse {
  defaults: Thresholds;
  meta: Record<string, ThresholdMeta>;
}
