import { PathViewer } from "@/components/PathViewer";
import type { Finding } from "@/lib/types";

export function FindingsList({ findings }: { findings: Finding[] }) {
  if (!findings.length) {
    return (
      <div className="rounded-xl border border-[#b9d7c8] bg-[#f1faf3] p-6 text-[#2c7652]">
        No confirmed privilege risks found in this inventory.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {findings.map((finding, index) => (
        <article key={`${finding.rule_id}-${finding.principal}-${index}`} className="rounded-xl border border-[#d4dfdc] bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-mono text-xs tracking-[0.18em] text-[#147d78]">{finding.rule_id}</p>
              <h3 className="mt-1 text-lg font-semibold text-[#17252f]">{finding.reason}</h3>
            </div>
            <span className="rounded-full border border-[#e2b7b1] bg-[#fff3f1] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#a33d34]">
              {finding.severity}
            </span>
          </div>
          <dl className="mt-4 grid gap-3 border-y border-[#e7eeeb] py-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[#71817e]">Principal</dt>
              <dd className="mt-1 break-all font-mono text-[#314842]">{finding.principal}</dd>
            </div>
            <div>
              <dt className="text-[#71817e]">Permission</dt>
              <dd className="mt-1 font-mono text-[#8a611b]">{finding.permission}</dd>
            </div>
          </dl>
          <div className="mt-5">
            <p className="mb-2 text-xs uppercase tracking-wider text-[#71817e]">Evidence path</p>
            <PathViewer path={finding.path} />
          </div>
          <p className="mt-5 text-sm text-[#536562]">
            <span className="font-semibold text-[#314842]">Recommended fix:</span> {finding.remediation}
          </p>
          {finding.confidence === "review_required" && (
            <p className="mt-3 text-xs text-[#8a611b]">This finding includes an IAM condition and needs policy-context review.</p>
          )}
        </article>
      ))}
    </div>
  );
}
