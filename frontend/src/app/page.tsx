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
    <main className="min-h-screen bg-[#070b14] px-5 py-10 text-slate-100 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-5 border-b border-slate-800 pb-8 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">CY-06 / Module 2.2</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white sm:text-5xl">Privilege Path Finder</h1>
            <p className="mt-3 max-w-2xl text-slate-400">Upload an AWS IAM authorization snapshot to reveal the exact relationships that create privilege risk.</p>
          </div>
          <div className="rounded-xl border border-cyan-900/60 bg-cyan-950/30 px-4 py-3 text-sm text-cyan-200">Read-only analysis</div>
        </header>

        <section className="mt-8 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
            <p className="text-sm font-semibold text-white">1. Load IAM data</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">Use JSON from AWS GetAccountAuthorizationDetails. Files stay local to this workflow.</p>
            <label className="mt-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-slate-600 bg-slate-950/60 px-5 py-10 text-center transition hover:border-cyan-400">
              <span className="text-sm font-medium text-cyan-200">Choose JSON file</span>
              <span className="mt-2 text-xs text-slate-500">Maximum 5 MB</span>
              <input className="sr-only" type="file" accept="application/json,.json" onChange={handleFile} />
            </label>
            {filename && <p className="mt-3 truncate font-mono text-xs text-slate-400">{filename}</p>}
            {loading && <p className="mt-5 text-sm text-cyan-300">Analyzing permissions…</p>}
            {error && <p className="mt-5 rounded-lg border border-red-900/70 bg-red-950/40 p-3 text-sm text-red-300">{error}</p>}
          </div>

          <div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Metric label="Findings" value={report?.summary.findings ?? "—"} />
              <Metric label="Critical" value={report?.summary.critical ?? "—"} tone="critical" />
              <Metric label="High" value={report?.summary.high ?? "—"} tone="high" />
            </div>
            <div className="mt-6">
              {report ? <FindingsList findings={report.findings} /> : <div className="rounded-2xl border border-slate-800 bg-slate-900/30 p-8 text-center text-sm text-slate-500">Your verified findings will appear here.</div>}
            </div>
            {report?.warnings.length ? <p className="mt-4 text-xs text-orange-300">{report.warnings.length} item(s) require review because the MVP cannot fully evaluate them.</p> : null}
          </div>
        </section>
        {inventory && <div className="mt-8 space-y-8"><IamGraph inventory={inventory} findings={report?.findings ?? []} /><InventoryTables inventory={inventory} /></div>}
      </div>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: number | string; tone?: "critical" | "high" }) {
  const color = tone === "critical" ? "text-red-300" : tone === "high" ? "text-orange-300" : "text-white";
  return <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className={`mt-2 text-3xl font-semibold ${color}`}>{value}</p></div>;
}
