"use client";

import { ChangeEvent, useState } from "react";

import { FindingsList } from "@/components/FindingsList";
import { IamGraph } from "@/components/IamGraph";
import { InventoryTables } from "@/components/InventoryTables";
import { analyzeInventory } from "@/lib/api";
import type { AnalysisReport, Inventory } from "@/lib/types";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

export default function Home() {
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [filename, setFilename] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    setReport(null);
    setInventory(null);
    setError("");

    if (file.size > MAX_FILE_BYTES) {
      setError("Input is too large. Maximum size is 5 MB.");
      return;
    }

    setLoading(true);
    try {
      const parsed = JSON.parse(await file.text()) as Inventory;
      setReport(await analyzeInventory(parsed));
      setInventory(parsed);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invalid JSON file.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f5f1] px-4 py-6 text-[#17252f] sm:px-8 sm:py-8 lg:px-12">
      <div className="mx-auto max-w-[1400px]">
        <header className="border-b border-[#cad6d2] pb-8">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-3 font-mono uppercase tracking-[0.22em] text-[#147d78]">
              <span className="h-2 w-2 rounded-full bg-[#147d78]" aria-hidden="true" />
              <span>CY—06</span><span className="text-[#b4c1bd]">/</span><span className="text-[#60716e]">IAM analysis</span>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#b9d7c8] bg-[#eaf5ed] px-3 py-1.5 font-medium text-[#2c7652]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#369264]" aria-hidden="true" /> Read-only mode
            </div>
          </div>
          <div className="mt-10 max-w-3xl">
            <h1 className="text-4xl font-semibold tracking-[-0.035em] text-[#17252f] sm:text-6xl">Privilege Path Finder</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[#536562] sm:text-lg">Trace how IAM permissions connect people, groups, roles, and policies—and surface the paths that create privilege risk.</p>
          </div>
        </header>

        <section className="mt-8 grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-stretch">
          <div className="rounded-xl border border-[#d4dfdc] bg-white p-6">
            <div className="flex items-start justify-between gap-4">
              <div><p className="text-sm font-semibold text-[#17252f]">Load IAM snapshot</p><p className="mt-1 text-xs leading-5 text-[#71817e]">Local JSON only · maximum 5 MB</p></div>
              <span className="rounded-md border border-[#d4dfdc] px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-[#71817e]">JSON</span>
            </div>
            <p className="mt-6 text-sm leading-6 text-[#536562]">Use output from AWS <span className="font-mono text-[#2f4641]">GetAccountAuthorizationDetails</span>. Credentials never enter this workflow.</p>
            <p className="mt-3 text-xs text-[#71817e]">Included sample is synthetic demo data for testing the graph.</p>
            <label htmlFor="iam-file" className="mt-6 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-[#9db3ad] bg-[#f7faf7] px-5 py-8 text-center transition hover:border-[#147d78] hover:bg-[#eef7f4] focus-within:border-[#147d78] focus-within:ring-2 focus-within:ring-[#147d78]/20">
              <svg className="mb-3 h-7 w-7 text-[#147d78]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <span className="text-sm font-medium text-[#147d78]">Choose JSON file</span>
              <span className="mt-2 text-xs text-[#71817e]">or use the sample in <span className="font-mono text-[#536562]">data/</span></span>
              <input id="iam-file" className="sr-only" type="file" accept="application/json,.json" onChange={handleFile} />
            </label>
            {filename && <p className="mt-4 truncate rounded-md bg-[#eef2ef] px-3 py-2 font-mono text-xs text-[#536562]" title={filename}>{filename}</p>}
            <div className="mt-5 min-h-5" aria-live="polite">
              {loading && <p className="text-sm text-[#147d78]">Analyzing permission paths…</p>}
              {error && <p className="rounded-lg border border-[#e2b7b1] bg-[#fff3f1] p-3 text-sm leading-5 text-[#a33d34]">{error}</p>}
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-5">
            <div className="overflow-hidden rounded-xl border border-[#d4dfdc] bg-white">
              <div className="grid grid-cols-3 divide-x divide-[#d4dfdc]">
                <Metric label="Findings" value={report?.summary.findings ?? "—"} />
                <Metric label="Critical" value={report?.summary.critical ?? "—"} tone="critical" />
                <Metric label="High" value={report?.summary.high ?? "—"} tone="high" />
              </div>
            </div>
            {inventory && <p className="font-mono text-xs text-[#60716e]">{count(inventory.UserDetailList)} users · {count(inventory.GroupDetailList)} groups · {count(inventory.RoleDetailList)} roles · {count(inventory.Policies)} policies</p>}
            {report && <CoverageSummary coverage={report.coverage} />}
            <div className="flex flex-1 items-center rounded-xl border border-dashed border-[#c7d3cf] bg-white p-7 sm:p-10">
              {report ? <div><p className="text-sm font-semibold text-[#17252f]">Snapshot ready for review</p><p className="mt-2 max-w-xl text-sm leading-6 text-[#60716e]">Use the graph to trace relationships, then use the findings rail to inspect evidence and recommended fixes.</p>{report.warnings.length ? <p className="mt-4 text-xs leading-5 text-[#8a611b]">{report.warnings.length} item(s) require review because some IAM conditions are not fully evaluated.</p> : null}</div> : <div><p className="text-sm font-medium text-[#314842]">No analysis loaded</p><p className="mt-2 text-sm leading-6 text-[#71817e]">Upload an IAM snapshot to see relationships, findings, and evidence paths.</p></div>}
            </div>
          </div>
        </section>
        {inventory && <div className="mt-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-[#cad6d2] pb-4">
            <div><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Analysis workspace</p><h2 className="mt-1 text-2xl font-semibold tracking-tight text-[#17252f]">See the access path, then decide</h2></div>
            <p className="max-w-md text-right text-sm leading-6 text-[#60716e]">Graph first for context. Findings rail for evidence. Tables below for source detail.</p>
          </div>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
            <IamGraph graph={report?.graph ?? { nodes: [], edges: [] }} findings={report?.findings ?? []} />
            <aside className="rounded-xl border border-[#d4dfdc] bg-white p-5" aria-labelledby="findings-heading">
              <div className="mb-5 flex items-center justify-between gap-3 border-b border-[#e3ebe7] pb-4"><div><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Risk review</p><h2 id="findings-heading" className="mt-1 text-xl font-semibold text-[#17252f]">Findings</h2></div><span className="font-mono text-xs text-[#71817e]">{report?.findings.length ?? 0} total</span></div>
              <FindingsList findings={report?.findings ?? []} />
            </aside>
          </div>
          <div className="mt-8"><InventoryTables inventory={inventory} identityMetadata={report?.identity_metadata ?? []} /></div>
        </div>}
      </div>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: number | string; tone?: "critical" | "high" }) {
  const color = tone === "critical" ? "text-[#b44339]" : tone === "high" ? "text-[#a36d13]" : "text-[#17252f]";
  return <div className="px-4 py-4 sm:px-5"><p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p><p className={`mt-2 text-2xl font-semibold tracking-tight ${color}`}>{value}</p></div>;
}

function count(value: unknown) {
  return Array.isArray(value) ? value.length : 0;
}

function CoverageSummary({ coverage }: { coverage: Record<string, number> }) {
  const items = [
    ["HR / IdP", coverage.identity_metadata],
    ["Resource policies", coverage.resource_policies],
    ["Boundaries", coverage.boundaries],
    ["SCPs", coverage.scp_policies],
    ["Sessions", coverage.sessions],
  ] as const;
  return <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">{items.map(([label, value]) => <div key={label} className="rounded-lg border border-[#dce5e1] bg-[#f7faf7] px-3 py-2"><p className="text-[10px] uppercase tracking-wider text-[#71817e]">{label}</p><p className="mt-1 font-mono text-sm font-semibold text-[#314842]">{value}</p></div>)}</div>;
}
