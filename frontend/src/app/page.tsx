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
    <main className="min-h-screen bg-[#071018] px-4 py-6 text-slate-100 sm:px-8 sm:py-8 lg:px-12">
      <div className="mx-auto max-w-[1400px]">
        <header className="border-b border-slate-800/90 pb-8">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-3 font-mono uppercase tracking-[0.22em] text-cyan-300">
              <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_14px_rgba(103,232,249,0.7)]" aria-hidden="true" />
              <span>CY—06</span><span className="text-slate-700">/</span><span className="text-slate-500">IAM analysis</span>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/5 px-3 py-1.5 font-medium text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" aria-hidden="true" /> Read-only mode
            </div>
          </div>
          <div className="mt-10 max-w-3xl">
            <h1 className="text-4xl font-semibold tracking-[-0.035em] text-white sm:text-6xl">Privilege Path Finder</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">Trace how IAM permissions connect people, groups, roles, and policies—and surface the paths that create privilege risk.</p>
          </div>
        </header>

        <section className="mt-8 grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start">
          <div className="rounded-2xl border border-slate-800 bg-[#0b1721] p-6">
            <div className="flex items-start justify-between gap-4">
              <div><p className="text-sm font-semibold text-white">Load IAM snapshot</p><p className="mt-1 text-xs leading-5 text-slate-500">Local JSON only · maximum 5 MB</p></div>
              <span className="rounded-md border border-slate-700 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-slate-500">JSON</span>
            </div>
            <p className="mt-6 text-sm leading-6 text-slate-400">Use output from AWS <span className="font-mono text-slate-300">GetAccountAuthorizationDetails</span>. Credentials never enter this workflow.</p>
            <label htmlFor="iam-file" className="mt-6 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-slate-600 bg-[#071018] px-5 py-8 text-center transition hover:border-cyan-300 hover:bg-cyan-300/[0.03] focus-within:border-cyan-300 focus-within:ring-2 focus-within:ring-cyan-300/20">
              <svg className="mb-3 h-7 w-7 text-cyan-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <span className="text-sm font-medium text-cyan-200">Choose JSON file</span>
              <span className="mt-2 text-xs text-slate-500">or use the sample in <span className="font-mono text-slate-400">data/</span></span>
              <input id="iam-file" className="sr-only" type="file" accept="application/json,.json" onChange={handleFile} />
            </label>
            {filename && <p className="mt-4 truncate rounded-lg bg-slate-950/60 px-3 py-2 font-mono text-xs text-slate-300" title={filename}>{filename}</p>}
            <div className="mt-5 min-h-5" aria-live="polite">
              {loading && <p className="text-sm text-cyan-300">Analyzing permission paths…</p>}
              {error && <p className="rounded-lg border border-red-900/70 bg-red-950/40 p-3 text-sm leading-5 text-red-300">{error}</p>}
            </div>
          </div>

          <div className="min-w-0">
            <div className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0b1721]">
              <div className="grid grid-cols-3 divide-x divide-slate-800">
                <Metric label="Findings" value={report?.summary.findings ?? "—"} />
                <Metric label="Critical" value={report?.summary.critical ?? "—"} tone="critical" />
                <Metric label="High" value={report?.summary.high ?? "—"} tone="high" />
              </div>
            </div>
            <div className="mt-5">
              {report ? <FindingsList findings={report.findings} /> : <div className="rounded-2xl border border-dashed border-slate-800 bg-[#0b1721]/60 p-10 text-center"><p className="text-sm font-medium text-slate-300">No analysis loaded</p><p className="mt-2 text-sm text-slate-500">Upload an IAM snapshot to see findings and evidence paths.</p></div>}
            </div>
            {report?.warnings.length ? <p className="mt-4 rounded-lg border border-orange-400/20 bg-orange-400/5 px-3 py-2 text-xs leading-5 text-orange-300">{report.warnings.length} item(s) require review because the current rules cannot fully evaluate them.</p> : null}
          </div>
        </section>
        {inventory && <div className="mt-8 space-y-6"><IamGraph inventory={inventory} findings={report?.findings ?? []} /><InventoryTables inventory={inventory} /></div>}
      </div>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: number | string; tone?: "critical" | "high" }) {
  const color = tone === "critical" ? "text-red-300" : tone === "high" ? "text-orange-300" : "text-white";
  return <div className="px-4 py-4 sm:px-5"><p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p><p className={`mt-2 text-2xl font-semibold tracking-tight ${color}`}>{value}</p></div>;
}
