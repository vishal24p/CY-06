import type { Finding, GraphEdge, GraphNode } from "@/lib/types";

type PositionedNode = GraphNode & { x: number; y: number; risky: boolean };

const columns = [
  { label: "Governance", types: ["organization", "root", "ou", "account"], x: 130, color: "#5b65a8" },
  { label: "Identities", types: ["user", "principal", "group", "identity_metadata"], x: 385, color: "#147d78" },
  { label: "Access controls", types: ["role", "policy", "boundary", "scp", "session", "session_policy"], x: 640, color: "#a36d13" },
  { label: "Resources", types: ["resource_policy", "resource"], x: 895, color: "#2c7652" },
];

export function IamGraph({ graph, findings }: { graph: { nodes: GraphNode[]; edges: GraphEdge[] }; findings: Finding[] }) {
  const riskPath = new Set(findings.flatMap((finding) => finding.path));
  const positioned = layoutNodes(graph.nodes, riskPath);
  const byId = new Map(positioned.map((node) => [node.id, node]));
  const edges = graph.edges.map((edge) => ({
    ...edge,
    from: byId.get(edge.from),
    to: byId.get(edge.to),
    risky: Boolean(byId.get(edge.from)?.risky || byId.get(edge.to)?.risky),
  })).filter((edge) => edge.from && edge.to);
  const height = Math.max(320, ...positioned.map((node) => node.y + 54));

  return (
    <section className="rounded-xl border border-[#d4dfdc] bg-white p-5" aria-labelledby="graph-heading">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Relationship map</p>
          <h2 id="graph-heading" className="mt-1 text-xl font-semibold text-[#17252f]">Authorization coverage graph</h2>
        </div>
        <p className="text-xs text-[#71817e]">API graph · red marks detected risk paths</p>
      </div>
      <div className="mt-5 overflow-x-auto rounded-lg border border-[#dce5e1] bg-[#f7faf7] p-3">
        <svg className="min-w-[1040px]" width="1040" height={height} viewBox={`0 0 1040 ${height}`} role="img" aria-labelledby="graph-heading graph-description">
          <desc id="graph-description">Governance, identities, access controls, resources, and their evidence-backed relationships.</desc>
          {columns.map((column) => <text key={column.label} x={column.x} y="25" textAnchor="middle" fill={column.color} fontSize="12" fontWeight="600">{column.label}</text>)}
          <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#849a94" /></marker></defs>
          {edges.map((edge, index) => {
            if (!edge.from || !edge.to) return null;
            const x1 = edge.from.x + 88;
            const y1 = edge.from.y + 24;
            const x2 = edge.to.x - 88;
            const y2 = edge.to.y + 24;
            return <g key={`${edge.from.id}-${edge.to.id}-${edge.type}-${index}`}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={edge.risky ? "#c9564c" : "#aebfba"} strokeWidth={edge.risky ? 3 : 1.5} markerEnd="url(#arrow)" />
              {edge.label && <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4} textAnchor="middle" fill="#71817e" fontSize="8">{truncate(edge.label, 18)}</text>}
            </g>;
          })}
          {positioned.map((node) => <g key={node.id}>
            <rect x={node.x - 88} y={node.y} width="176" height="48" rx="6" fill={node.risky ? "#fff3f1" : "#ffffff"} stroke={node.risky ? "#c9564c" : kindColor(node.type)} strokeWidth={node.risky ? 2 : 1} />
            <text x={node.x} y={node.y + 20} textAnchor="middle" fill="#17252f" fontSize="11" fontWeight="600">{truncate(node.label, 24)}</text>
            <text x={node.x} y={node.y + 36} textAnchor="middle" fill={node.risky ? "#a33d34" : "#71817e"} fontSize="9">{node.risky ? "risk path" : node.type.replaceAll("_", " ")}</text>
          </g>)}
        </svg>
      </div>
    </section>
  );
}

function layoutNodes(nodes: GraphNode[], riskPath: Set<string>): PositionedNode[] {
  return columns.flatMap((column) => column.types.flatMap((type) => nodes.filter((node) => node.type === type)))
    .map((node) => {
      const column = columns.find((candidate) => candidate.types.includes(node.type)) ?? columns[1];
      const index = nodes.filter((candidate) => column.types.includes(candidate.type)).indexOf(node);
      const risky = riskPath.has(node.id) || riskPath.has(node.label) || [...riskPath].some((value) => value.endsWith(node.id));
      return { ...node, x: column.x, y: 52 + index * 70, risky };
    });
}

function kindColor(type: string) { return columns.find((column) => column.types.includes(type))?.color ?? "#64748b"; }
function truncate(value: string, length: number) { return value.length > length ? `${value.slice(0, length - 1)}…` : value; }
