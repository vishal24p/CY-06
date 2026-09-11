import type { AnalysisReport } from "@/lib/types";

const coverageLabels: Record<string, string> = {
  identity_metadata: "Employee details",
  resource_policies: "Data access rules",
  boundaries: "Access limits",
  scp_policies: "Organization restrictions",
  sessions: "Temporary access",
};

export function AnalysisSummary({ report }: { report: AnalysisReport }) {
  return (
    <section className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.8fr)]" aria-label="Analysis evidence summary">
      <div className="rounded-xl border border-[#d4dfdc] bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <div><p className="font-mono text-xs uppercase tracking-[0.18em] text-[#147d78]">Supporting data</p><h2 className="mt-1 text-lg font-semibold text-[#17252f]">What informed this result</h2></div>
          <span className="rounded-full bg-[#eef7f4] px-3 py-1 text-xs font-semibold text-[#147d78]">{report.graph.nodes.length} nodes · {report.graph.edges.length} links</span>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-5">
          {Object.entries(coverageLabels).map(([key, label]) => <div key={key} className="rounded-lg bg-[#f4f7f4] p-3"><p className="text-[11px] leading-4 text-[#71817e]">{label}</p><p className="mt-1 text-xl font-semibold text-[#17252f]">{report.coverage[key] ?? 0}</p></div>)}
        </div>
      </div>
      <div className="rounded-xl border border-[#d4dfdc] bg-white p-5">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#a36d13]">Data limitations</p>
        <h2 className="mt-1 text-lg font-semibold text-[#17252f]">Check before acting</h2>
        {report.warnings.length ? <ul className="mt-3 space-y-2 text-sm leading-5 text-[#536562]">{report.warnings.slice(0, 4).map((warning, index) => <li key={`${warning.code ?? "warning"}-${index}`}><span className="font-mono text-xs text-[#8a611b]">{warning.code ?? "review_required"}</span> {warning.reason ?? warning.feature ?? "Some policy context is incomplete."}</li>)}</ul> : <p className="mt-3 text-sm leading-5 text-[#536562]">All modeled inputs were available for this analysis.</p>}
        {report.warnings.length > 4 && <p className="mt-3 text-xs text-[#71817e]">+ {report.warnings.length - 4} more notes in source evidence.</p>}
      </div>
    </section>
  );
}
