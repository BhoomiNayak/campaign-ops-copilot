"""Recommendation engine.

Converts a finding category into evidence-based, plain-English investigation
steps. Recommendations are deliberately phrased as things to *check* — the tool
identifies potential problems, it never asserts a confirmed root cause.
"""

from __future__ import annotations

from ..models import FindingCategory


# Each entry is a list of concrete, non-speculative next steps. They suggest
# what to investigate, not what "caused" the issue.
_RECOMMENDATIONS: dict[FindingCategory, list[str]] = {
    FindingCategory.elevated_bounce: [
        "Review the recipient list for this campaign for stale, guessed, or scraped addresses.",
        "Check whether list verification was run before sending.",
        "Segment bounces into hard vs. soft (if your ESP exposes this) to see which dominates.",
        "Confirm the sending domain's SPF, DKIM, and DMARC records are valid.",
    ],
    FindingCategory.bounce_spike: [
        "Compare the recipient sources between the current and prior period.",
        "Check for a recent change in sending domain, IP, or ESP configuration.",
        "Verify no large batch of low-quality addresses was added before the spike.",
        "Review ESP or postmaster notifications around the spike date.",
    ],
    FindingCategory.declining_replies: [
        "Compare messaging/subject lines between the current and prior period.",
        "Confirm reply tracking is configured correctly and not under-counting.",
        "Check whether audience targeting or list quality changed.",
        "Review send timing and volume changes that could affect engagement.",
    ],
    FindingCategory.low_replies: [
        "Review whether reply tracking is wired up correctly for this campaign.",
        "Assess message relevance and call-to-action clarity for the target audience.",
        "Confirm messages are landing in the inbox rather than spam (seed tests).",
    ],
    FindingCategory.repeated_issue: [
        "Treat this campaign/domain as a priority given the recurring pattern.",
        "Look for a common structural cause across the affected periods (list source, template, domain health).",
        "Consider pausing or reducing volume until the underlying issue is understood.",
    ],
    FindingCategory.incomplete_data: [
        "Confirm the export includes all reporting columns for every send.",
        "Check the ESP/integration for dropped fields or partial exports.",
        "Re-export the affected period once reporting is complete for accurate metrics.",
    ],
}


def recommendations_for(category: FindingCategory) -> list[str]:
    """Return the investigation steps for a finding category."""
    return list(_RECOMMENDATIONS.get(category, []))
