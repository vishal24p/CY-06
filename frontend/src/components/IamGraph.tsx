import type { Finding, Inventory } from "@/lib/types";

type Kind = "user" | "group" | "role" | "policy";
type Node = { id: string; label: string; kind: Kind; x: number; y: number; risky: boolean };
type Edge = { from: string; to: string; risky: boolean };

const columns: Array<{ kind: Kind; label: string; x: number; color: string }> = [
  { kind: "user", label: "Users", x: 110, color: "#67e8f9" },
  { kind: "group", label: "Groups", x: 330, color: "#a5b4fc" },
  { kind: "role", label: "Roles", x: 550, color: "#fbbf24" },
  { kind: "policy", label: "Policies", x: 770, color: "#86efac" },
];

export function IamGraph({ inventory, findings }: { inventory: Inventory; findings: Finding[] }) {
  const riskPath = new Set(findings.flatMap((finding) => finding.path));
  const nodes: Node[] = [];
  const byKey = new Map<string, Node>();

  for (const column of columns) {
    const records = recordsFor(inventory, column.kind);
    records.forEach((record, index) => {
      const id = recordId(record, column.kind, index);
      const node = {
        id,
        label: recordLabel(record, column.kind, index),
        kind: column.kind,
        x: column.x,
        y: 72 + index * 76,
        risky: riskPath.has(id) || riskPath.has(recordLabel(record, column.kind, index)),
      } satisfies Node;
      nodes.push(node);
      byKey.set(id, node);
      byKey.set(recordLabel(record, column.kind, index), node);
      if (column.kind === "policy") byKey.set(`policy:${recordLabel(record, column.kind, index)}`, node);
    });
  }

  const edges = buildEdges(inventory, byKey, riskPath);
  const height = Math.max(300, ...nodes.map((node) => node.y + 48));

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5" aria-labelledby="graph-heading">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">Relationship map</p>
          <h2 id="graph-heading" className="mt-1 text-xl font-semibold text-white">IAM privilege graph</h2>
        </div>
        <p className="text-xs text-slate-500">Red edges/nodes are part of a detected risk path.</p>
      </div>
      <div className="mt-5 overflow-x-auto rounded-xl border border-slate-800 bg-[#070b14] p-3">
        <svg className="min-w-[860px]" width="900" height={height} viewBox={`0 0 900 ${height}`} role="img" aria-labelledby="graph-heading graph-description">
          <desc id="graph-description">Users, groups, roles, and policies connected by IAM relationships.</desc>
          {columns.map((column) => <text key={column.kind} x={column.x} y="25" textAnchor="middle" fill={column.color} fontSize="12" fontWeight="600">{column.label}</text>)}
          {edges.map((edge, index) => {
            const from = byKey.get(edge.from);
            const to = byKey.get(edge.to);
            if (!from || !to) return null;
            return <line key={`${edge.from}-${edge.to}-${index}`} x1={from.x + 78} y1={from.y + 22} x2={to.x - 78} y2={to.y + 22} stroke={edge.risky ? "#f87171" : "#334155"} strokeWidth={edge.risky ? 3 : 1.5} markerEnd="url(#arrow)" />;
          })}
          <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b" /></marker></defs>
          {nodes.map((node) => <g key={node.id}>
            <rect x={node.x - 78} y={node.y} width="156" height="44" rx="7" fill={node.risky ? "#451a1a" : "#0f172a"} stroke={node.risky ? "#f87171" : kindColor(node.kind)} strokeWidth={node.risky ? 2 : 1} />
            <text x={node.x} y={node.y + 18} textAnchor="middle" fill="#f8fafc" fontSize="11" fontWeight="600">{truncate(node.label, 22)}</text>
            <text x={node.x} y={node.y + 33} textAnchor="middle" fill={node.risky ? "#fca5a5" : "#64748b"} fontSize="9">{node.risky ? "risk path" : node.kind}</text>
          </g>)}
        </svg>
      </div>
    </section>
  );
}

function recordsFor(inventory: Inventory, kind: Kind): Record<string, unknown>[] {
  const key = kind === "user" ? "UserDetailList" : kind === "group" ? "GroupDetailList" : kind === "role" ? "RoleDetailList" : "Policies";
  return Array.isArray(inventory[key]) ? inventory[key].filter(isRecord) : [];
}

function recordId(record: Record<string, unknown>, kind: Kind, index: number) {
  return stringValue(record.Arn) ?? `${kind}-${index}`;
}

function recordLabel(record: Record<string, unknown>, kind: Kind, index: number) {
  const key = kind === "user" ? "UserName" : kind === "group" ? "GroupName" : kind === "role" ? "RoleName" : "PolicyName";
  return stringValue(record[key]) ?? recordId(record, kind, index);
}

function buildEdges(inventory: Inventory, byKey: Map<string, Node>, riskPath: Set<string>): Edge[] {
  const edges: Edge[] = [];
  const add = (from: string | undefined, to: string | undefined) => {
    if (!from || !to || !byKey.has(from) || !byKey.has(to)) return;
    if (edges.some((edge) => edge.from === from && edge.to === to)) return;
    edges.push({ from, to, risky: riskPath.has(from) || riskPath.has(to) });
  };

  for (const user of recordsFor(inventory, "user")) {
    const userId = stringValue(user.Arn) ?? stringValue(user.UserName);
    for (const group of arrayValue(user.GroupList)) add(userId, stringValue(group) ?? (isRecord(group) ? stringValue(group.GroupName) : undefined));
    for (const policy of [...arrayValue(user.AttachedManagedPolicies), ...arrayValue(user.UserPolicyList)]) add(userId, `policy:${policyName(policy)}`);
    for (const policy of arrayValue(user.UserPolicyList)) {
      for (const statement of policyStatements(policy)) {
        const resource = statement.Resource;
        if (statement.Action === "sts:AssumeRole") add(userId, stringValue(resource));
      }
    }
  }
  for (const group of recordsFor(inventory, "group")) {
    const groupId = stringValue(group.Arn) ?? stringValue(group.GroupName);
    for (const user of arrayValue(group.Users)) add(groupId, stringValue(user) ?? (isRecord(user) ? stringValue(user.Arn) ?? stringValue(user.UserName) : undefined));
    for (const policy of [...arrayValue(group.AttachedManagedPolicies), ...arrayValue(group.GroupPolicyList)]) add(groupId, `policy:${policyName(policy)}`);
  }
  for (const role of recordsFor(inventory, "role")) {
    const roleId = stringValue(role.Arn) ?? stringValue(role.RoleName);
    for (const policy of [...arrayValue(role.AttachedManagedPolicies), ...arrayValue(role.RolePolicyList)]) add(roleId, `policy:${policyName(policy)}`);
    for (const statement of trustStatements(role.AssumeRolePolicyDocument)) {
      const principal = statement.Principal;
      add(stringValue(principal) ?? (isRecord(principal) ? stringValue(principal.AWS) : undefined), roleId);
    }
  }
  return edges;
}

function policyName(value: unknown) { return isRecord(value) ? stringValue(value.PolicyName) ?? stringValue(value.Name) ?? "policy" : stringValue(value) ?? "policy"; }
function policyStatements(value: unknown) { return isRecord(value) && isRecord(value.PolicyDocument) ? arrayValue(value.PolicyDocument.Statement).filter(isRecord) : []; }
function trustStatements(value: unknown) { return isRecord(value) ? arrayValue(value.Statement).filter(isRecord) : []; }
function arrayValue(value: unknown): unknown[] { return Array.isArray(value) ? value : value === undefined ? [] : [value]; }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function stringValue(value: unknown): string | undefined { return typeof value === "string" ? value : undefined; }
function truncate(value: string, length: number) { return value.length > length ? `${value.slice(0, length - 1)}…` : value; }
function kindColor(kind: Kind) { return columns.find((column) => column.kind === kind)?.color ?? "#64748b"; }
