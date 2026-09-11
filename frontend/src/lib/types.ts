export type Finding = {
  rule_id: string;
  severity: "critical" | "high";
  principal: string;
  permission: string;
  resource: string;
  path: string[];
  reason: string;
  remediation: string;
  confidence: "confirmed" | "review_required";
};

export type PrivilegePath = {
  principal: string;
  target: string;
  risk: "critical" | "high";
  risk_score: number;
  score_breakdown: Record<string, number>;
  starting_privilege: "low" | "elevated";
  hops: number;
  path: string[];
  permission: string;
  reason: string;
  remediation: {
    policy_name: string;
    statement_index: number;
    action: string;
    resource: string;
  };
  confidence: "confirmed" | "review_required";
};

export type GraphNode = {
  id: string;
  type: string;
  label: string;
  source: string;
};

export type GraphEdge = {
  from: string;
  to: string;
  type: string;
  label?: string;
  evidence?: string;
};

export type IdentityMetadata = {
  principal_arn: string;
  employee_id: string;
  display_name: string;
  job_title: string;
  department: string;
  manager: string;
  employment_type: string;
  status: string;
  identity_provider: string;
};

export type AnalysisReport = {
  status: "ok";
  summary: {
    findings: number;
    paths: number;
    critical: number;
    high: number;
  };
  findings: Finding[];
  paths: PrivilegePath[];
  warnings: Array<Record<string, string>>;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  coverage: Record<string, number>;
  identity_metadata: IdentityMetadata[];
};

export type Inventory = Record<string, unknown> & {
  UserDetailList?: unknown[];
  GroupDetailList?: unknown[];
  RoleDetailList?: unknown[];
  Policies?: unknown[];
  IdentityMetadata?: unknown[];
  ResourcePolicies?: unknown[];
  Organizations?: unknown;
  Sessions?: unknown[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatToolCall = {
  name: string;
  status: "completed";
};

export type ChatResponse = {
  message: string;
  tool_calls: ChatToolCall[];
};
