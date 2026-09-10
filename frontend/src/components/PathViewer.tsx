export function PathViewer({ path }: { path: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Privilege path">
      {path.map((step, index) => (
        <span key={`${step}-${index}`} className="flex items-center gap-2">
          <span className="rounded-md border border-[#c7d3cf] bg-[#f4f7f4] px-2.5 py-1 font-mono text-xs text-[#314842]">
            {step}
          </span>
          {index < path.length - 1 && <span className="text-[#91a49e]">→</span>}
        </span>
      ))}
    </div>
  );
}
