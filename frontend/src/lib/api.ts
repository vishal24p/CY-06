import type { AnalysisReport } from "@/lib/types";

export async function analyzeInventory(inventory: unknown): Promise<AnalysisReport> {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inventory, context: {} }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail ?? "Analysis failed.");
  }
  return normalizeReport(payload);
}

function normalizeReport(payload: unknown): AnalysisReport {
  const value = isRecord(payload) ? payload : {};
  const summary = isRecord(value.summary) ? value.summary : {};
  const coverage = isRecord(value.coverage) ? value.coverage : {};
  const graph = isRecord(value.graph) ? value.graph : {};
  return {
    status: "ok",
    summary: {
      findings: number(summary.findings),
      critical: number(summary.critical),
      high: number(summary.high),
    },
    findings: Array.isArray(value.findings) ? value.findings as AnalysisReport["findings"] : [],
    warnings: Array.isArray(value.warnings) ? value.warnings as AnalysisReport["warnings"] : [],
    graph: {
      nodes: Array.isArray(graph.nodes) ? graph.nodes as AnalysisReport["graph"]["nodes"] : [],
      edges: Array.isArray(graph.edges) ? graph.edges as AnalysisReport["graph"]["edges"] : [],
    },
    coverage: {
      identity_metadata: number(coverage.identity_metadata),
      resource_policies: number(coverage.resource_policies),
      boundaries: number(coverage.boundaries),
      scp_policies: number(coverage.scp_policies),
      sessions: number(coverage.sessions),
    },
    identity_metadata: Array.isArray(value.identity_metadata) ? value.identity_metadata as AnalysisReport["identity_metadata"] : [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function number(value: unknown) { return typeof value === "number" ? value : 0; }
