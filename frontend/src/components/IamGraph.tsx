"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Finding, GraphEdge, GraphNode } from "@/lib/types";

type LayoutSize = { width: number; height: number };
type PositionedNode = GraphNode & { x: number; y: number; radius: number; risky: boolean; color: string };
type PositionedEdge = Omit<GraphEdge, "from" | "to"> & { from: PositionedNode; to: PositionedNode; risky: boolean };

const DEFAULT_SIZE: LayoutSize = { width: 1024, height: 640 };
const PALETTE = ["#dc3f47", "#2e9fd0", "#159879", "#8c5bd6", "#e18a20", "#e65a98", "#5b65a8", "#3b8f62"];

export function IamGraph({ graph, findings }: { graph: { nodes: GraphNode[]; edges: GraphEdge[] }; findings: Finding[] }) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const riskPath = useMemo(() => new Set(findings.flatMap((finding) => finding.path)), [findings]);
  const types = useMemo(() => [...new Set(graph.nodes.map((node) => node.type))].sort(), [graph.nodes]);
  const colors = useMemo(() => new Map(types.map((type, index) => [type, PALETTE[index % PALETTE.length]])), [types]);
  const positioned = useMemo(() => layoutNodes(graph.nodes, graph.edges, riskPath, size, colors), [graph.nodes, graph.edges, riskPath, size, colors]);
  const byId = useMemo(() => new Map(positioned.map((node) => [node.id, node])), [positioned]);
  const edges = useMemo<PositionedEdge[]>(() => graph.edges.flatMap((edge) => {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    return from && to ? [{ ...edge, from, to, risky: from.risky || to.risky }] : [];
  }), [graph.edges, byId]);

  useEffect(() => {
    if (!canvasRef.current) return;
    const updateSize = () => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect && rect.width > 0 && rect.height > 0) setSize({ width: Math.round(rect.width), height: Math.round(rect.height) });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(canvasRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section className="flex h-full min-h-0 flex-col rounded-xl border border-[#d4dfdc] bg-white p-5" aria-labelledby="graph-heading">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Relationship map</p>
          <h2 id="graph-heading" className="mt-1 text-xl font-semibold text-[#17252f]">Authorization coverage graph</h2>
        </div>
        <p className="text-xs text-[#71817e]">Topology layout · red marks detected risk paths</p>
      </div>

      <div ref={canvasRef} className="relative mt-5 min-h-0 flex-1 overflow-hidden rounded-lg border border-[#dce5e1] bg-[#f8faf9]">
        <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-lg border border-[#dce5e1] bg-white/95 px-3 py-2 text-xs text-[#60716e] shadow-sm">
          <span className="font-semibold text-[#314842]">{graph.nodes.length}</span> nodes · <span className="font-semibold text-[#314842]">{graph.edges.length}</span> edges
        </div>
        <div className="pointer-events-none absolute bottom-4 left-4 z-10 max-h-36 max-w-[min(260px,calc(100%-2rem))] overflow-y-auto rounded-lg border border-[#dce5e1] bg-white/95 p-3 shadow-sm">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[#71817e]">Legend</p>
          <div className="grid gap-1.5">
            {types.map((type) => <div key={type} className="flex items-center gap-2 text-xs text-[#536562]"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: colors.get(type) }} />{formatType(type)}</div>)}
          </div>
        </div>
        <svg className="h-full w-full" viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-labelledby="graph-heading graph-description">
          <desc id="graph-description">A responsive topology map of identity, policy, resource, and organization relationships.</desc>
          <defs><marker id="graph-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="#9aaba6" /></marker></defs>
          {edges.map((edge, index) => <line key={`${edge.from.id}-${edge.to.id}-${edge.type}-${index}`} x1={edge.from.x} y1={edge.from.y} x2={edge.to.x} y2={edge.to.y} stroke={edge.risky ? "#c9564c" : "#9aaba6"} strokeOpacity={edge.risky ? 0.78 : 0.3} strokeWidth={edge.risky ? 2.2 : 1.1} markerEnd="url(#graph-arrow)" />)}
          {positioned.map((node) => <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
            <circle r={node.radius + 4} fill={node.risky ? "#fff1ef" : "#ffffff"} opacity="0.95" />
            <circle r={node.radius} fill={node.risky ? "#dc3f47" : node.color} stroke={node.risky ? "#a33d34" : "#ffffff"} strokeWidth={node.risky ? 2 : 1.5} />
            <text y={node.radius + 14} textAnchor="middle" fill="#536562" fontSize="10">{truncate(node.label, 22)}</text>
          </g>)}
        </svg>
      </div>
    </section>
  );
}

function layoutNodes(nodes: GraphNode[], edges: GraphEdge[], riskPath: Set<string>, size: LayoutSize, colors: Map<string, string>): PositionedNode[] {
  if (!nodes.length) return [];
  const padding = 48;
  const width = Math.max(size.width, padding * 2 + 1);
  const height = Math.max(size.height, padding * 2 + 1);
  const minDistance = Math.max(42, Math.sqrt((width * height) / nodes.length) * 0.55);
  const positions = nodes.map((node) => {
    const angle = seededUnit(`${node.id}:angle`) * Math.PI * 2;
    const radius = Math.min(width, height) * (0.12 + seededUnit(`${node.id}:radius`) * 0.28);
    const risky = riskPath.has(node.id) || riskPath.has(node.label) || [...riskPath].some((value) => value.endsWith(node.id));
    return { node, x: width / 2 + Math.cos(angle) * radius + (seededUnit(`${node.id}:x`) - 0.5) * width * 0.2, y: height / 2 + Math.sin(angle) * radius + (seededUnit(`${node.id}:y`) - 0.5) * height * 0.2, radius: risky ? 9 : 6, risky };
  });
  const indexById = new Map(nodes.map((node, index) => [node.id, index]));
  const links = edges.flatMap((edge) => {
    const from = indexById.get(edge.from);
    const to = indexById.get(edge.to);
    return from === undefined || to === undefined ? [] : [{ from, to }];
  });

  // ponytail: O(n²) repulsion keeps this dependency-free; move to a worker if graphs exceed ~300 nodes.
  for (let iteration = 0; iteration < 90; iteration += 1) {
    const delta = positions.map(() => ({ x: 0, y: 0 }));
    for (let first = 0; first < positions.length; first += 1) {
      for (let second = first + 1; second < positions.length; second += 1) {
        const dx = positions[first].x - positions[second].x;
        const dy = positions[first].y - positions[second].y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const force = Math.min(20, (minDistance * minDistance) / (distance * 260));
        const x = (dx / distance) * force;
        const y = (dy / distance) * force;
        delta[first].x += x;
        delta[first].y += y;
        delta[second].x -= x;
        delta[second].y -= y;
      }
    }
    for (const link of links) {
      const from = positions[link.from];
      const to = positions[link.to];
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const force = (distance - minDistance * 1.7) * 0.012;
      const x = (dx / distance) * force;
      const y = (dy / distance) * force;
      delta[link.from].x += x;
      delta[link.from].y += y;
      delta[link.to].x -= x;
      delta[link.to].y -= y;
    }
    for (const [index, position] of positions.entries()) {
      delta[index].x += (width / 2 - position.x) * 0.004;
      delta[index].y += (height / 2 - position.y) * 0.004;
      position.x = clamp(position.x + delta[index].x, padding, width - padding);
      position.y = clamp(position.y + delta[index].y, padding, height - padding);
    }
  }

  return positions.map(({ node, x, y, radius, risky }) => ({ ...node, x, y, radius, risky, color: colors.get(node.type) ?? "#64748b" }));
}

function seededUnit(value: string) {
  let hash = 2166136261;
  for (const character of value) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
  return (hash >>> 0) / 4294967295;
}

function clamp(value: number, minimum: number, maximum: number) { return Math.min(Math.max(value, minimum), maximum); }
function formatType(value: string) { return value.replaceAll("_", " ").replace(/(^|\s)\w/g, (letter) => letter.toUpperCase()); }
function truncate(value: string, length: number) { return value.length > length ? `${value.slice(0, length - 1)}…` : value; }
