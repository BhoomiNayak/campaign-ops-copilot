"""Report and export generation.

Produces three downloadable artifacts from a dataset + its findings:
  * campaign summary CSV   -> summary_csv()
  * findings CSV           -> findings_csv()
  * print-friendly HTML    -> audit_report_html()

All outputs are self-contained strings/bytes with no external dependencies, and
include the reporting period, metrics, thresholds, and data-quality warnings.
"""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone

from ..config import Thresholds, thresholds_as_dict
from ..models import CampaignMetrics, DatasetSummary, Finding


def summary_csv(summary: DatasetSummary, campaigns: list[CampaignMetrics]) -> str:
    """CSV containing the dataset summary followed by per-campaign rows."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["Campaign Ops Copilot - Campaign Summary"])
    writer.writerow(["reporting_period", f"{summary.period_start} to {summary.period_end}"])
    writer.writerow(["total_sent", summary.total_sent])
    writer.writerow(["total_bounced", summary.total_bounced])
    writer.writerow(["total_replies", summary.total_replies])
    writer.writerow(["overall_bounce_rate", f"{summary.bounce_rate:.4f}"])
    writer.writerow(
        ["overall_reply_rate", f"{summary.reply_rate:.4f}", f"(denominator: {summary.reply_rate_denominator})"]
    )
    writer.writerow(["num_campaigns", summary.num_campaigns])
    writer.writerow([])

    writer.writerow(
        [
            "campaign_name",
            "domain",
            "sent",
            "delivered",
            "bounced",
            "replies",
            "bounce_rate",
            "reply_rate",
            "reply_rate_denominator",
            "periods",
        ]
    )
    for c in campaigns:
        writer.writerow(
            [
                c.campaign_name,
                c.domain or "",
                c.sent,
                c.delivered if c.delivered is not None else "",
                c.bounced,
                c.replies,
                f"{c.bounce_rate:.4f}",
                f"{c.reply_rate:.4f}",
                c.reply_rate_denominator,
                c.periods,
            ]
        )
    return buf.getvalue()


def findings_csv(findings: list[Finding]) -> str:
    """CSV of all findings with evidence and recommendations."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "severity",
            "category",
            "campaign_name",
            "domain",
            "metric",
            "evidence",
            "explanation",
            "confidence",
            "threshold_used",
            "data_limitations",
            "status",
            "recommendations",
        ]
    )
    for f in findings:
        writer.writerow(
            [
                f.id,
                f.severity.value,
                f.category.value,
                f.campaign_name or "",
                f.domain or "",
                f.metric,
                f.evidence,
                f.explanation,
                f.confidence.value,
                f.threshold_used or "",
                f.data_limitations or "",
                f.status.value,
                " | ".join(f.recommendations),
            ]
        )
    return buf.getvalue()


def audit_report_html(
    summary: DatasetSummary,
    campaigns: list[CampaignMetrics],
    findings: list[Finding],
    insufficient_notes: list[str],
    thresholds: Thresholds,
) -> str:
    """A self-contained, print-friendly HTML audit report."""
    e = html.escape
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    th = thresholds_as_dict(thresholds)

    sev_color = {"high": "#b91c1c", "medium": "#b45309", "low": "#2563eb", "info": "#4b5563"}

    findings_rows = ""
    for f in findings:
        color = sev_color.get(f.severity.value, "#4b5563")
        recs = "".join(f"<li>{e(r)}</li>" for r in f.recommendations)
        comparison = ""
        if f.comparison:
            comparison = (
                f"<div class='cmp'>Comparison ({e(f.comparison.label)}): "
                f"prior {f.comparison.prior_value:.4f} ({e(f.comparison.prior_period or '')}) → "
                f"current {f.comparison.current_value:.4f} ({e(f.comparison.current_period or '')})</div>"
            )
        findings_rows += f"""
        <div class="finding">
          <div class="finding-head">
            <span class="sev" style="background:{color}">{e(f.severity.value.upper())}</span>
            <strong>{e(f.title)}</strong>
            <span class="cat">{e(f.category.value)}</span>
          </div>
          <div class="meta">Campaign: {e(f.campaign_name or '—')} &nbsp;|&nbsp; Domain: {e(f.domain or '—')}
            &nbsp;|&nbsp; Confidence: {e(f.confidence.value)} &nbsp;|&nbsp; Status: {e(f.status.value)}</div>
          <div><em>Metric:</em> {e(f.metric)} &nbsp; <em>Threshold:</em> {e(f.threshold_used or '—')}</div>
          <div class="evidence"><strong>Evidence:</strong> {e(f.evidence)}</div>
          <div>{e(f.explanation)}</div>
          {comparison}
          {f"<div class='limit'><strong>Data limitations:</strong> {e(f.data_limitations)}</div>" if f.data_limitations else ""}
          <div><strong>Recommended checks:</strong><ul>{recs}</ul></div>
        </div>"""

    if not findings:
        findings_rows = "<p>No findings were detected under the current thresholds.</p>"

    campaign_rows = "".join(
        f"<tr><td>{e(c.campaign_name)}</td><td>{e(c.domain or '')}</td>"
        f"<td>{c.sent}</td><td>{c.bounced}</td><td>{c.replies}</td>"
        f"<td>{c.bounce_rate*100:.1f}%</td>"
        f"<td>{c.reply_rate*100:.1f}% ({e(c.reply_rate_denominator)})</td></tr>"
        for c in campaigns
    )

    insufficient_html = ""
    if insufficient_notes:
        items = "".join(f"<li>{e(n)}</li>" for n in insufficient_notes)
        insufficient_html = f"<h2>Data-quality notes</h2><ul class='notes'>{items}</ul>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Campaign Ops Copilot — Audit Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; color:#111; margin:32px; line-height:1.45; }}
  h1 {{ margin-bottom:4px; }}
  .sub {{ color:#555; margin-top:0; }}
  table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:14px; }}
  th, td {{ border:1px solid #ddd; padding:6px 8px; text-align:left; }}
  th {{ background:#f5f7fb; }}
  .kpis {{ display:flex; gap:16px; flex-wrap:wrap; margin:12px 0; }}
  .kpi {{ border:1px solid #e5e7eb; border-radius:8px; padding:10px 14px; min-width:140px; }}
  .kpi .v {{ font-size:22px; font-weight:700; }}
  .kpi .l {{ color:#666; font-size:12px; }}
  .finding {{ border:1px solid #e5e7eb; border-left:4px solid #999; border-radius:6px; padding:12px; margin:12px 0; }}
  .finding-head {{ display:flex; align-items:center; gap:10px; }}
  .sev {{ color:#fff; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:700; }}
  .cat {{ color:#666; font-size:12px; }}
  .meta {{ color:#555; font-size:13px; margin:4px 0; }}
  .evidence {{ margin:6px 0; }}
  .cmp, .limit {{ background:#f8fafc; padding:6px 8px; border-radius:4px; margin:6px 0; font-size:13px; }}
  .banner {{ background:#fff7ed; border:1px solid #fed7aa; padding:8px 12px; border-radius:6px; font-size:13px; }}
  @media print {{ .finding {{ page-break-inside: avoid; }} }}
</style></head>
<body>
  <h1>Campaign Ops Copilot — Audit Report</h1>
  <p class="sub">Generated {e(generated)} &nbsp;|&nbsp; Reporting period: {e(str(summary.period_start))} to {e(str(summary.period_end))}</p>
  <div class="banner">Rule-based analysis. Findings identify <strong>potential</strong> issues to investigate;
    they do not assert a confirmed root cause. If the dataset is synthetic demo data, treat all values as illustrative.</div>

  <h2>Key metrics</h2>
  <div class="kpis">
    <div class="kpi"><div class="v">{summary.total_sent:,}</div><div class="l">Total sent</div></div>
    <div class="kpi"><div class="v">{summary.total_bounced:,}</div><div class="l">Total bounced</div></div>
    <div class="kpi"><div class="v">{summary.bounce_rate*100:.1f}%</div><div class="l">Bounce rate</div></div>
    <div class="kpi"><div class="v">{summary.total_replies:,}</div><div class="l">Total replies</div></div>
    <div class="kpi"><div class="v">{summary.reply_rate*100:.1f}%</div><div class="l">Reply rate ({e(summary.reply_rate_denominator)})</div></div>
    <div class="kpi"><div class="v">{summary.num_campaigns}</div><div class="l">Campaigns</div></div>
    <div class="kpi"><div class="v">{len(findings)}</div><div class="l">Findings</div></div>
  </div>

  <h2>Campaign comparison</h2>
  <table>
    <thead><tr><th>Campaign</th><th>Domain</th><th>Sent</th><th>Bounced</th><th>Replies</th><th>Bounce rate</th><th>Reply rate</th></tr></thead>
    <tbody>{campaign_rows}</tbody>
  </table>

  <h2>Findings &amp; recommendations</h2>
  {findings_rows}

  {insufficient_html}

  <h2>Thresholds used</h2>
  <table>
    <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
    <tbody>{''.join(f'<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>' for k, v in th.items())}</tbody>
  </table>
</body></html>"""
