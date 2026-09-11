"use client";

import { useEffect, useRef, useState } from "react";

import { simulateRemediation } from "@/lib/api";
import type { AnalysisReport, Finding, Inventory, PrivilegePath } from "@/lib/types";

type RemediationTarget = Finding | PrivilegePath;

export function RemediationPreview({ inventory, target, onPreview }: { inventory: Inventory; target: RemediationTarget; onPreview: (report: AnalysisReport) => void }) {
  const [preview, setPreview] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(true);
  const locator = pathRemediation(target);

  useEffect(() => () => {
    active.current = false;
  }, []);

  async function handlePreview() {
    setLoading(true);
    setError("");
    try {
      const next = await simulateRemediation(inventory, target);
      if (!active.current) return;
      setPreview(next);
      onPreview(next);
    } catch (cause) {
      if (!active.current) return;
      setError(cause instanceof Error ? cause.message : "Could not preview remediation.");
    } finally {
      if (active.current) setLoading(false);
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-[#b9d7c8] bg-[#f1faf3] p-5" aria-labelledby="remediation-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><p className="font-mono text-xs uppercase tracking-[0.18em] text-[#2c7652]">Safe what-if</p><h2 id="remediation-heading" className="mt-1 text-lg font-semibold text-[#17252f]">Preview the fix</h2><p className="mt-1 max-w-2xl text-sm leading-5 text-[#536562]">Remove <span className="font-mono">{locator?.action ?? target.permission}</span> from a copy of this snapshot and run the same analyzer again.</p></div>
        <button type="button" onClick={handlePreview} disabled={loading} className="rounded-md bg-[#2c7652] px-4 py-2 text-sm font-semibold text-white hover:bg-[#225e40] disabled:cursor-not-allowed disabled:bg-[#9db3ad]">{loading ? "Re-analyzing…" : "Preview safe fix"}</button>
      </div>
      {error && <p className="mt-3 text-sm text-[#a33d34]" role="alert">{error}</p>}
      {preview && <div className="mt-4 grid gap-3 sm:grid-cols-3" aria-live="polite"><div className="rounded-lg bg-white p-3"><p className="text-xs text-[#71817e]">Remediation</p><p className="mt-1 break-words text-sm font-semibold text-[#17252f]">{locator?.policy_name ?? "No exact policy"}</p><p className="mt-1 break-words font-mono text-xs text-[#536562]">{locator?.action ?? target.permission} · {locator?.resource ?? "unknown resource"}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs text-[#71817e]">Selected path</p><p className="mt-1 text-2xl font-semibold text-[#2c7652]">{pathStillPresent(preview, target) ? "Still present" : "Broken"}</p><p className="text-xs text-[#71817e]">same analyzer</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs text-[#71817e]">Remaining paths</p><p className="mt-1 text-2xl font-semibold text-[#17252f]">{preview.paths.length}</p><p className="text-xs text-[#71817e]">local copy only</p></div></div>}
    </section>
  );
}

function pathStillPresent(report: AnalysisReport, target: RemediationTarget) {
  if ("target" in target) return report.paths.some((path) => path.path.join("\u0000") === target.path.join("\u0000"));
  return report.findings.some((finding) => finding.permission === target.permission && finding.principal === target.principal);
}

function pathRemediation(target: RemediationTarget): PrivilegePath["remediation"] | null {
  return typeof target.remediation === "object" && target.remediation !== null ? target.remediation : null;
}
