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

export type AnalysisReport = {
  status: "ok";
  summary: {
    findings: number;
    critical: number;
    high: number;
  };
  findings: Finding[];
  warnings: Array<Record<string, string>>;
};

export type Inventory = Record<string, unknown> & {
  UserDetailList?: unknown[];
  GroupDetailList?: unknown[];
  RoleDetailList?: unknown[];
  Policies?: unknown[];
};
