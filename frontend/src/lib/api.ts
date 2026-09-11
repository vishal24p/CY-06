import type { AnalysisReport, ChatMessage, ChatResponse, Finding, Inventory, PrivilegePath } from "@/lib/types";

export async function loadDemoInventory(): Promise<Inventory> {
  const response = await fetch("/api/analyze", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok || !isRecord(payload)) throw new Error(payload.detail ?? "Demo data unavailable.");
  return payload as Inventory;
}

export async function loadFullDemoInventory(): Promise<Inventory> {
  const response = await fetch("/api/full-demo", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok || !isRecord(payload)) throw new Error(payload.detail ?? "Full inventory unavailable.");
  return payload as Inventory;
}

export async function loadLiveInventory(): Promise<{ inventory: Inventory; report: AnalysisReport }> {
  const response = await fetch("/api/live", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok || !isRecord(payload)) throw new Error(payload.detail ?? "Live AWS inventory unavailable.");
  if (!isRecord(payload.inventory)) throw new Error("Live AWS inventory unavailable.");
  return { inventory: payload.inventory as Inventory, report: normalizeReport(payload.report) };
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

export async function simulateRemediation(inventory: Inventory, target: Finding | PrivilegePath): Promise<AnalysisReport> {
  if (!hasRemediationLocator(target)) {
    throw new Error("Select an attack path before previewing this remediation.");
  }

  const copy = JSON.parse(JSON.stringify(inventory)) as Inventory;
  const policies = findPolicies(copy, target.remediation.policy_name);
  if (policies.length !== 1) {
    throw new Error(policies.length ? "Remediation policy is ambiguous; preview was not applied." : "Remediation policy could not be located; preview was not applied.");
  }
  if (!removeActionFromStatement(
    policies[0],
    target.remediation.statement_index,
    target.remediation.action,
    target.remediation.resource,
  )) {
    throw new Error("Remediation action could not be located in its policy statement; preview was not applied.");
  }
  return analyzeInventory(copy);
}

function hasRemediationLocator(target: Finding | PrivilegePath): target is PrivilegePath {
  return typeof target.remediation === "object" && target.remediation !== null;
}

function findPolicies(value: unknown, policyName: string): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.flatMap((item) => findPolicies(item, policyName));
  if (!isRecord(value)) return [];
  return [
    ...(value.PolicyName === policyName && isRecord(value.PolicyDocument) ? [value] : []),
    ...Object.values(value).flatMap((item) => findPolicies(item, policyName)),
  ];
}

function removeActionFromStatement(policy: Record<string, unknown>, statementIndex: number, action: string, resource: string): boolean {
  const document = policy.PolicyDocument;
  if (!isRecord(document)) return false;
  const statements = Array.isArray(document.Statement) ? document.Statement : [document.Statement];
  const statement = statements[statementIndex];
  if (!isRecord(statement)) return false;
  const resources = Array.isArray(statement.Resource) ? statement.Resource : [statement.Resource];
  if (!resources.includes(resource)) return false;
  if (statement.Action === action) {
    statement.Action = [];
    return true;
  }
  if (!Array.isArray(statement.Action) || !statement.Action.includes(action)) return false;
  statement.Action = statement.Action.filter((item) => item !== action);
  return true;
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
      paths: number(summary.paths),
      critical: number(summary.critical),
      high: number(summary.high),
    },
    findings: Array.isArray(value.findings) ? value.findings as AnalysisReport["findings"] : [],
    paths: Array.isArray(value.paths) ? value.paths as AnalysisReport["paths"] : [],
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
