import { PathViewer } from "@/components/PathViewer";
import type { Finding } from "@/lib/types";

export function FindingsList({ findings }: { findings: Finding[] }) {
  if (!findings.length) {
    return (
      <div className="rounded-2xl border border-emerald-900/70 bg-emerald-950/30 p-6 text-emerald-200">
        No confirmed privilege risks found in this inventory.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {findings.map((finding, index) => (
        <article key={`${finding.rule_id}-${finding.principal}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5 shadow-xl shadow-black/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-mono text-xs tracking-[0.18em] text-cyan-300">{finding.rule_id}</p>
              <h3 className="mt-1 text-lg font-semibold text-white">{finding.reason}</h3>
            </div>
            <span className="rounded-full border border-red-500/40 bg-red-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-red-300">
              {finding.severity}
            </span>
          </div>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">Principal</dt>
              <dd className="mt-1 break-all font-mono text-slate-200">{finding.principal}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Permission</dt>
              <dd className="mt-1 font-mono text-amber-200">{finding.permission}</dd>
            </div>
          </dl>
          <div className="mt-5">
            <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">Evidence path</p>
            <PathViewer path={finding.path} />
          </div>
          <p className="mt-5 border-t border-slate-800 pt-4 text-sm text-slate-300">
            <span className="font-semibold text-slate-100">Recommended fix:</span> {finding.remediation}
          </p>
          {finding.confidence === "review_required" && (
            <p className="mt-3 text-xs text-orange-300">This finding includes an IAM condition and needs policy-context review.</p>
          )}
        </article>
      ))}
    </div>
  );
}
