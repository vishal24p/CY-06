import type { PrivilegePath } from "@/lib/types";

const factorLabels: Record<string, string> = {
  target_impact: "Target impact",
  assumption_resource_breadth: "Resource breadth",
  hop_directness: "Directness",
  source_context: "Source context",
  confidence: "Confidence",
};

export function PrivilegePathList({ paths, selectedIndex, onSelect }: { paths: PrivilegePath[]; selectedIndex: number; onSelect: (index: number) => void }) {
  if (!paths.length) return null;

  return (
    <section className="mt-6 rounded-xl border border-[#d4dfdc] bg-white p-5" aria-labelledby="ranked-paths-heading">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#a33d34]">Ranked by analyzer</p>
        <h2 id="ranked-paths-heading" className="mt-1 text-lg font-semibold text-[#17252f]">Attack paths</h2>
      </div>
      <ol className="mt-4 space-y-3">
        {paths.map((path, index) => {
          const selected = index === selectedIndex;
          return <li key={path.path.join("\u0000")}>
            <button type="button" onClick={() => onSelect(index)} aria-pressed={selected} className={`w-full rounded-lg border p-4 text-left transition ${selected ? "border-[#a33d34] bg-[#fff8f6]" : "border-[#d4dfdc] hover:border-[#9db3ad] hover:bg-[#f7faf7]"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-sm font-semibold text-[#17252f]">Path {index + 1} · {path.hops} {path.hops === 1 ? "hop" : "hops"}</p><p className="mt-1 text-sm text-[#536562]">{path.reason}</p></div>
                <span className="rounded-full bg-[#a33d34] px-3 py-1 text-sm font-semibold text-white">Score {path.risk_score}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
                <span className="rounded-full bg-[#eef7f4] px-2.5 py-1 text-[#147d78]">Starts {path.starting_privilege}</span>
                <span className="rounded-full bg-[#f4f7f4] px-2.5 py-1 text-[#536562]">{path.confidence === "confirmed" ? "Confirmed" : "Review required"}</span>
                {Object.entries(path.score_breakdown).map(([factor, score]) => <span key={factor} className="rounded-full bg-[#fffaf0] px-2.5 py-1 text-[#8a611b]">{factorLabels[factor] ?? factor}: +{score}</span>)}
              </div>
            </button>
          </li>;
        })}
      </ol>
    </section>
  );
}
