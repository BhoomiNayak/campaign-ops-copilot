import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FindingsTable } from "./FindingsTable";
import type { Finding } from "../types";

const findings: Finding[] = [
  {
    id: "f1",
    campaign_name: "Cold List",
    domain: "coldlist.example.com",
    severity: "high",
    category: "elevated_bounce",
    title: "Elevated bounce rate for 'Cold List'",
    metric: "bounce_rate",
    evidence: "Bounce rate 12.0% over 2000 sent.",
    explanation: "The lifetime bounce rate is 12.0%.",
    recommendations: ["Review the recipient list for stale addresses."],
    comparison: null,
    confidence: "high",
    data_limitations: null,
    threshold_used: "bounce_rate >= 10.0%",
    status: "Open",
  },
  {
    id: "f2",
    campaign_name: "Reactivation",
    domain: null,
    severity: "medium",
    category: "declining_replies",
    title: "Declining reply rate for 'Reactivation'",
    metric: "reply_rate",
    evidence: "Reply rate fell from 6.0% to 2.0%.",
    explanation: "Reply rate declined.",
    recommendations: ["Compare subject lines."],
    comparison: null,
    confidence: "medium",
    data_limitations: null,
    threshold_used: "relative_reply_decline >= 30.0%",
    status: "Open",
  },
];

describe("FindingsTable", () => {
  it("renders all findings and count", () => {
    render(<FindingsTable findings={findings} insufficientNotes={[]} onStatusChange={vi.fn()} />);
    expect(screen.getByText(/Findings/)).toBeInTheDocument();
    expect(screen.getByText(/Elevated bounce rate for 'Cold List'/)).toBeInTheDocument();
    expect(screen.getByText(/Declining reply rate for 'Reactivation'/)).toBeInTheDocument();
  });

  it("filters by severity", () => {
    render(<FindingsTable findings={findings} insufficientNotes={[]} onStatusChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Filter by severity"), { target: { value: "high" } });
    expect(screen.getByText(/Elevated bounce rate for 'Cold List'/)).toBeInTheDocument();
    expect(screen.queryByText(/Declining reply rate/)).not.toBeInTheDocument();
  });

  it("expands a finding to reveal recommendations", () => {
    render(<FindingsTable findings={findings} insufficientNotes={[]} onStatusChange={vi.fn()} />);
    const toggles = screen.getAllByLabelText("Toggle details");
    fireEvent.click(toggles[0]);
    expect(screen.getByText(/Review the recipient list for stale addresses/)).toBeInTheDocument();
  });

  it("calls onStatusChange when a status is changed", () => {
    const onStatusChange = vi.fn();
    render(<FindingsTable findings={findings} insufficientNotes={[]} onStatusChange={onStatusChange} />);
    const select = screen.getByLabelText(/Status for Elevated bounce rate/);
    fireEvent.change(select, { target: { value: "Resolved" } });
    expect(onStatusChange).toHaveBeenCalledWith("f1", "Resolved");
  });

  it("shows insufficient-data notes when present", () => {
    render(
      <FindingsTable
        findings={findings}
        insufficientNotes={["'Tiny': insufficient volume to compare periods."]}
        onStatusChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/Data-quality notes/)).toBeInTheDocument();
    expect(screen.getByText(/insufficient volume to compare periods/)).toBeInTheDocument();
  });

  it("shows an empty message when filters match nothing", () => {
    render(<FindingsTable findings={findings} insufficientNotes={[]} onStatusChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Filter by campaign"), { target: { value: "Cold List" } });
    fireEvent.change(screen.getByLabelText("Filter by severity"), { target: { value: "medium" } });
    expect(screen.getByText(/No findings match the current filters/)).toBeInTheDocument();
    expect(screen.queryByText(/Elevated bounce rate for 'Cold List'/)).not.toBeInTheDocument();
  });
});
