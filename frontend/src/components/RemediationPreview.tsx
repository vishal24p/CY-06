"use client";

import { useState } from "react";

import { simulateRemediation } from "@/lib/api";
import type { AnalysisReport, Finding, Inventory } from "@/lib/types";

export function RemediationPreview({ inventory, finding }: { inventory: Inventory; finding: Finding }) {
  const [preview, setPreview] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handlePreview() {
    setLoading(true);
    setError("");
    try {
      setPreview(await simulateRemediation(inventory, finding));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not preview remediation.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-[#b9d7c8] bg-[#f1faf3] p-5" aria-labelledby="remediation-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><p className="font-mono text-xs uppercase tracking-[0.18em] text-[#2c7652]">Safe what-if</p><h2 id="remediation-heading" className="mt-1 text-lg font-semibold text-[#17252f]">Preview the fix</h2><p className="mt-1 max-w-2xl text-sm leading-5 text-[#536562]">Remove <span className="font-mono">{finding.permission}</span> from a copy of this snapshot and run the same analyzer again.</p></div>
        <button type="button" onClick={handlePreview} disabled={loading} className="rounded-md bg-[#2c7652] px-4 py-2 text-sm font-semibold text-white hover:bg-[#225e40] disabled:cursor-not-allowed disabled:bg-[#9db3ad]">{loading ? "Re-analyzing…" : "Preview safe fix"}</button>
      </div>
      {error && <p className="mt-3 text-sm text-[#a33d34]" role="alert">{error}</p>}
      {preview && <div className="mt-4 grid gap-3 sm:grid-cols-3" aria-live="polite"><div className="rounded-lg bg-white p-3"><p className="text-xs text-[#71817e]">Before</p><p className="mt-1 text-2xl font-semibold text-[#a33d34]">{1}</p><p className="text-xs text-[#71817e]">selected path</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs text-[#71817e]">After</p><p className="mt-1 text-2xl font-semibold text-[#2c7652]">{preview.findings.some((item) => item.permission === finding.permission && item.principal === finding.principal) ? "Still present" : "Removed"}</p><p className="text-xs text-[#71817e]">same analyzer</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs text-[#71817e]">Scope</p><p className="mt-1 text-sm font-semibold text-[#17252f]">Local copy only</p><p className="text-xs text-[#71817e]">nothing applied</p></div></div>}
    </section>
  );
}
