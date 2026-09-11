"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Finding, GraphEdge, GraphNode, IdentityMetadata } from "@/lib/types";

type LayoutSize = { width: number; height: number };
type PositionedNode = GraphNode & { displayLabel: string; subtitle?: string; x: number; y: number; width: number; height: number; risky: boolean; color: string };
type PositionedEdge = Omit<GraphEdge, "from" | "to"> & { from: PositionedNode; to: PositionedNode; risky: boolean };

const DEFAULT_SIZE: LayoutSize = { width: 1200, height: 720 };
const MIN_ZOOM = 0.55;
const MAX_ZOOM = 2.4;

export function IamGraph({ graph, findings, identityMetadata = [], afterGraph, afterFindings }: { graph: { nodes: GraphNode[]; edges: GraphEdge[] }; findings: Finding[]; identityMetadata?: IdentityMetadata[]; afterGraph?: { nodes: GraphNode[]; edges: GraphEdge[] }; afterFindings?: Finding[] }) {
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const [zoom, setZoom] = useState(1);
  const [showAfter, setShowAfter] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; pan: { x: number; y: number } } | null>(null);
  const activeGraph = showAfter && afterGraph ? afterGraph : graph;
  const activeFindings = showAfter && afterFindings ? afterFindings : findings;
  const visibleNodes = useMemo(() => activeGraph.nodes.filter((node) => node.type !== "identity_metadata"), [activeGraph.nodes]);
  const graphSize = useMemo(() => layoutSize(visibleNodes, size), [visibleNodes, size]);
  const riskPath = useMemo(() => new Set(activeFindings.flatMap((finding) => finding.path)), [activeFindings]);
  const personDetails = useMemo(() => new Map(identityMetadata.map((item) => [item.principal_arn, { name: item.display_name, subtitle: [item.job_title, item.department].filter(Boolean).join(" · ") }])), [identityMetadata]);
  const positioned = useMemo(() => layoutNodes(visibleNodes, riskPath, graphSize, personDetails), [visibleNodes, riskPath, graphSize, personDetails]);
  const byId = useMemo(() => new Map(positioned.map((node) => [node.id, node])), [positioned]);
  const edges = useMemo<PositionedEdge[]>(() => activeGraph.edges.flatMap((edge) => { const from = byId.get(edge.from); const to = byId.get(edge.to); return from && to ? [{ ...edge, from, to, risky: activeFindings.some((finding) => finding.path.some((value, index, path) => index < path.length - 1 && pathTokenMatches(value, from) && pathTokenMatches(path[index + 1], to))) }] : []; }), [activeGraph.edges, activeFindings, byId]);
  const selected = positioned.find((node) => node.id === selectedId);

  useEffect(() => {
    if (!canvasRef.current) return;
    const updateSize = () => { const rect = canvasRef.current?.getBoundingClientRect(); if (rect && rect.width > 0 && rect.height > 0) setSize({ width: Math.round(rect.width), height: Math.round(rect.height) }); };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(canvasRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const updateFullscreen = () => setIsFullscreen(document.fullscreenElement === sectionRef.current);
    document.addEventListener("fullscreenchange", updateFullscreen);
    return () => document.removeEventListener("fullscreenchange", updateFullscreen);
  }, []);

  async function toggleFullscreen() {
    if (!sectionRef.current) return;
    if (document.fullscreenElement) await document.exitFullscreen();
    else await sectionRef.current?.requestFullscreen();
  }

  function handleWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    setZoom((value) => clamp(value + (event.deltaY < 0 ? 0.1 : -0.1), MIN_ZOOM, MAX_ZOOM));
  }

  return (
    <section ref={sectionRef} className="flex h-full min-h-0 flex-col rounded-xl border border-[#d4dfdc] bg-white p-5" aria-labelledby="graph-heading">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Supporting evidence</p><h2 id="graph-heading" className="mt-1 text-xl font-semibold text-[#17252f]">All access relationships</h2><p className="mt-1 text-xs text-[#71817e]">Use this wider map to inspect access outside the selected route.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          {afterGraph && <div className="flex rounded-md border border-[#c7d3cf] bg-[#f4f7f4] p-0.5" role="group" aria-label="Graph comparison"><button type="button" onClick={() => setShowAfter(false)} className={`rounded px-2.5 py-1 text-xs ${!showAfter ? "bg-white font-semibold text-[#147d78] shadow-sm" : "text-[#60716e]"}`}>Before</button><button type="button" onClick={() => setShowAfter(true)} className={`rounded px-2.5 py-1 text-xs ${showAfter ? "bg-white font-semibold text-[#2c7652] shadow-sm" : "text-[#60716e]"}`}>After preview</button></div>}
          <div className="flex items-center rounded-md border border-[#c7d3cf] bg-white" role="group" aria-label="Graph zoom"><button type="button" aria-label="Zoom out" onClick={() => setZoom((value) => clamp(value - 0.15, MIN_ZOOM, MAX_ZOOM))} className="px-2.5 py-1.5 text-lg text-[#536562] hover:bg-[#f4f7f4]">−</button><span className="min-w-12 border-x border-[#dce5e1] px-2 text-center font-mono text-[11px] text-[#71817e]">{Math.round(zoom * 100)}%</span><button type="button" aria-label="Zoom in" onClick={() => setZoom((value) => clamp(value + 0.15, MIN_ZOOM, MAX_ZOOM))} className="px-2.5 py-1.5 text-lg text-[#536562] hover:bg-[#f4f7f4]">+</button></div>
          <button type="button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="rounded-md border border-[#c7d3cf] px-2.5 py-1.5 text-xs text-[#536562] hover:bg-[#f4f7f4]">Reset</button>
          <button type="button" onClick={toggleFullscreen} className="rounded-md border border-[#147d78] px-2.5 py-1.5 text-xs font-semibold text-[#147d78] hover:bg-[#eef7f4]">{isFullscreen ? "Exit full screen" : "Full screen"}</button>
        </div>
      </div>

      <div ref={canvasRef} onWheel={handleWheel} className="relative mt-5 min-h-0 flex-1 overflow-auto rounded-lg border border-[#dce5e1] bg-[#f8faf9]" aria-label="Interactive authorization graph. Use zoom controls or mouse wheel.">
        <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-lg border border-[#dce5e1] bg-white/95 px-3 py-2 text-xs text-[#60716e] shadow-sm"><span className="font-semibold text-[#314842]">{positioned.length}</span> nodes · <span className="font-semibold text-[#314842]">{edges.length}</span> edges <span className="ml-2 text-[#71817e]">· {showAfter ? "projected state" : "current state"}</span></div>
        {selected && <div className="absolute right-4 top-4 z-10 max-w-64 rounded-lg border border-[#147d78] bg-white/95 p-3 shadow-sm"><p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#147d78]">Selected node</p><p className="mt-1 break-words text-sm font-semibold text-[#17252f]">{selected.displayLabel}</p><p className="mt-1 text-xs text-[#71817e]">{formatType(selected.type)} · {selected.source}</p></div>}
        <svg className="h-full cursor-grab active:cursor-grabbing" style={{ minWidth: graphSize.width }} viewBox={`0 0 ${graphSize.width} ${graphSize.height}`} role="img" aria-labelledby="graph-heading graph-description" onPointerDown={(event) => { if ((event.target as Element).closest('[role="button"]')) return; event.currentTarget.setPointerCapture(event.pointerId); dragRef.current = { x: event.clientX, y: event.clientY, pan }; }} onPointerMove={(event) => { if (!dragRef.current) return; setPan({ x: dragRef.current.pan.x + event.clientX - dragRef.current.x, y: dragRef.current.pan.y + event.clientY - dragRef.current.y }); }} onPointerUp={() => { dragRef.current = null; }} onPointerCancel={() => { dragRef.current = null; }}>
          <desc id="graph-description">Aligned authorization map with identities, policies, resources, and evidence context. Red edges indicate detected risk paths.</desc>
          <defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2c7652" /></marker><marker id="graph-risk-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#c9564c" /></marker></defs>
          <g transform={`translate(${graphSize.width / 2 + pan.x} ${graphSize.height / 2 + pan.y}) scale(${zoom}) translate(${-graphSize.width / 2} ${-graphSize.height / 2})`}>
            {laneHeaders(graphSize).map((lane) => <g key={lane.label}><line x1={lane.x} y1={52} x2={lane.x} y2={graphSize.height - 48} stroke="#dce5e1" strokeDasharray="3 8" /><text x={lane.x} y={28} textAnchor="middle" fill="#91a49e" fontSize="10" fontWeight="600" letterSpacing="1.4">{lane.label.toUpperCase()}</text></g>)}
            {edges.map((edge, index) => <path key={`${edge.from.id}-${edge.to.id}-${edge.type}-${index}`} d={edgePath(edge)} fill="none" stroke={edge.risky ? "#c9564c" : "#2c7652"} strokeOpacity={edge.risky ? 0.92 : 0.72} strokeWidth={edge.risky ? 2.5 : 1.8} markerEnd={`url(#${edge.risky ? "graph-risk-arrow" : "graph-arrow"})`} />)}
            {positioned.map((node) => <g key={node.id} transform={`translate(${node.x} ${node.y})`} role="button" tabIndex={0} aria-label={`${node.displayLabel}${node.subtitle ? `, ${node.subtitle}` : ""}, ${formatType(node.type)}`} onClick={() => setSelectedId(node.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedId(node.id); }} className="cursor-pointer"><title>{node.displayLabel}{node.subtitle ? ` · ${node.subtitle}` : ""}</title><NodeShape node={node} color={node.risky ? "#c9564c" : node.color} /><text y={node.subtitle ? -5 : 4} textAnchor="middle" fill={node.risky ? "#ffffff" : "#17252f"} fontSize="10" fontWeight="600">{truncate(node.displayLabel, 21)}</text>{node.subtitle && <text y={10} textAnchor="middle" fill={node.risky ? "#fff4f1" : "#60716e"} fontSize="7">{truncate(node.subtitle, 28)}</text>}</g>)}
          </g>
        </svg>
      </div>
    </section>
  );
}

function layoutSize(nodes: GraphNode[], size: LayoutSize): LayoutSize {
  const maxRows = Math.max(countRows(nodes), 1);
  return { width: Math.max(size.width, 1420), height: Math.max(size.height, 150 + maxRows * 74) };
}

function countRows(nodes: GraphNode[]) {
  const rows = new Array(5).fill(0);
  for (const node of nodes) rows[layerFor(node.type)] += 1;
  return Math.max(...rows);
}

function layoutNodes(nodes: GraphNode[], riskPath: Set<string>, size: LayoutSize, personDetails: Map<string, { name: string; subtitle: string }>): PositionedNode[] {
  if (!nodes.length) return [];
  const paddingX = 92;
  const usableWidth = Math.max(size.width - paddingX * 2, 1);
  const columns = 5;
  const groups = Array.from({ length: columns }, () => [] as GraphNode[]);
  for (const node of nodes) groups[layerFor(node.type)].push(node);
  const maxRows = Math.max(...groups.map((group) => group.length), 1);
  const rowGap = Math.max(66, Math.min(78, (size.height - 120) / maxRows));
  return groups.flatMap((group, column) => group.sort((a, b) => a.label.localeCompare(b.label)).map((node, row) => {
    const risky = isRisky(node, riskPath);
    const person = node.type === "user" ? personDetails.get(node.id.replace(/^user:/, "")) : undefined;
    return { ...node, displayLabel: person?.name || node.label, subtitle: person?.subtitle || undefined, x: paddingX + (usableWidth / (columns - 1)) * column, y: 84 + rowGap * row, width: nodeWidth(), height: nodeHeight(), risky, color: strokeFor() };
  }));
}

function layerFor(type: string) { return type === "user" || type === "identity_metadata" ? 0 : type === "group" || type === "role" || type === "session" ? 1 : type === "policy" || type === "boundary" || type === "session_policy" || type === "resource_policy" || type === "scp" ? 2 : type === "resource" ? 3 : 4; }
function laneHeaders(size: LayoutSize) { const start = 92; const gap = Math.max(size.width - start * 2, 1) / 4; return [{ label: "People", x: start }, { label: "Relationships", x: start + gap }, { label: "Policies", x: start + gap * 2 }, { label: "Resources", x: start + gap * 3 }, { label: "Context", x: start + gap * 4 }]; }
function nodeWidth() { return 122; }
function nodeHeight() { return 52; }
function edgePath(edge: PositionedEdge) {
  const sameLane = Math.abs(edge.from.x - edge.to.x) < 1;
  if (sameLane) {
    const downward = edge.from.y < edge.to.y;
    const fromY = edge.from.y + (downward ? edge.from.height / 2 : -edge.from.height / 2);
    const toY = edge.to.y + (downward ? -edge.to.height / 2 : edge.to.height / 2);
    return `M ${edge.from.x} ${fromY} L ${edge.to.x} ${toY}`;
  }
  const forward = edge.from.x < edge.to.x;
  const fromX = edge.from.x + (forward ? edge.from.width / 2 : -edge.from.width / 2);
  const toX = edge.to.x - (forward ? edge.to.width / 2 : -edge.to.width / 2);
  const bend = fromX + (toX - fromX) / 2;
  return `M ${fromX} ${edge.from.y} C ${bend} ${edge.from.y}, ${bend} ${edge.to.y}, ${toX} ${edge.to.y}`;
}

function NodeShape({ node, color }: { node: PositionedNode; color: string }) {
  const fill = node.risky ? color : "#ffffff";
  const stroke = node.risky ? "#a33d34" : color;
  return <rect x={-node.width / 2} y={-node.height / 2} width={node.width} height={node.height} rx="5" fill={fill} stroke={stroke} strokeWidth={node.risky ? 3 : 2} />;
}

function isRisky(node: GraphNode, riskPath: Set<string>) { return riskPath.has(node.id) || riskPath.has(node.label) || [...riskPath].some((value) => value === node.id.replace(/^(user|group|role):/, "") || value.endsWith(`/${node.label}`)); }
function pathTokenMatches(value: string, node: PositionedNode) { return [node.id, node.label, node.id.replace(/^[^:]+:/, "")].some((candidate) => value === candidate || value.endsWith(`/${candidate}`) || value.endsWith(`:${candidate}`)); }
function strokeFor() { return "#74847f"; }
function clamp(value: number, minimum: number, maximum: number) { return Math.min(Math.max(value, minimum), maximum); }
function formatType(value: string) { return value.replaceAll("_", " ").replace(/(^|\s)\w/g, (letter) => letter.toUpperCase()); }
function truncate(value: string, length: number) { return value.length > length ? `${value.slice(0, length - 1)}…` : value; }
