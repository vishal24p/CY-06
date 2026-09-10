export function PathViewer({ path }: { path: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Privilege path">
      {path.map((step, index) => (
        <span key={`${step}-${index}`} className="flex items-center gap-2">
          <span className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 font-mono text-xs text-slate-200">
            {step}
          </span>
          {index < path.length - 1 && <span className="text-slate-600">→</span>}
        </span>
      ))}
    </div>
  );
}
