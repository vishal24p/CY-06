import type { AnalysisReport, ChatMessage, ChatResponse, Finding, Inventory } from "@/lib/types";

export async function loadDemoInventory(): Promise<Inventory> {
  const response = await fetch("/api/analyze", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok || !isRecord(payload)) throw new Error(payload.detail ?? "Demo data unavailable.");
  return payload as Inventory;
}

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

export async function sendChat(messages: ChatMessage[]): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail ?? "Chat failed.");
  }
  return normalizeChatResponse(payload);
}

export async function simulateRemediation(inventory: Inventory, finding: Finding): Promise<AnalysisReport> {
  const copy = JSON.parse(JSON.stringify(inventory)) as Inventory;
  removeAction(copy, finding.permission);
  return analyzeInventory(copy);
}

function removeAction(value: unknown, action: string): void {
  if (Array.isArray(value)) {
    value.forEach((item) => removeAction(item, action));
    return;
  }
  if (!isRecord(value)) return;
  if (typeof value.Action === "string" && value.Action === action) value.Action = [];
  if (Array.isArray(value.Action)) value.Action = value.Action.filter((item) => item !== action);
  Object.values(value).forEach((item) => removeAction(item, action));
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

function normalizeChatResponse(payload: unknown): ChatResponse {
  const value = isRecord(payload) ? payload : {};
  const toolCalls = value.tool_calls;
  return {
    message: typeof value.message === "string" ? value.message : "",
    tool_calls: Array.isArray(toolCalls) && toolCalls.every((tool) => isRecord(tool) && typeof tool.name === "string")
      ? toolCalls.map((tool) => ({ name: (tool as { name: string }).name, status: "completed" }))
      : [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function number(value: unknown) { return typeof value === "number" ? value : 0; }
