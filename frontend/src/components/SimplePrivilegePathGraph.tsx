import type { IdentityMetadata, PrivilegePath } from "@/lib/types";

export function SimplePrivilegePathGraph({ path, identityMetadata = [], previewed, afterPath }: { path: PrivilegePath; identityMetadata?: IdentityMetadata[]; previewed: boolean; afterPath?: PrivilegePath }) {
  const person = identityMetadata.find((item) => item.principal_arn === path.principal);
  const steps = path.path.map((step, index) => ({
    key: `${step}-${index}`,
    label: stepLabel(step, identityMetadata),
    type: stepType(step, index, path.path.length),
    detail: stepDetail(step, person, index, path.path.length),
  }));
  const displaySteps = [...steps, { key: "impact", label: "Full admin access", type: "impact", detail: "Can control protected systems" }];

  return (
    <section className="rounded-xl border border-[#e2b7b1] bg-[#fff8f6] p-5" aria-labelledby="simple-path-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#a33d34]">One access route</p>
          <h2 id="simple-path-heading" className="mt-1 text-xl font-semibold text-[#17252f]">How {person?.display_name || shortName(path.principal)} reaches full admin access</h2>
          {person && <p className="mt-1 text-sm font-medium text-[#60716e]">{[person.job_title, person.department].filter(Boolean).join(" · ")}</p>}
        </div>
        <span className="rounded-full bg-[#a33d34] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white">High risk</span>
      </div>

      <div className="mt-5 overflow-x-auto rounded-lg border border-[#e2b7b1] bg-white p-4">
        <ol className="flex min-w-max items-center justify-center gap-2" aria-label="Simple privilege path">
          {displaySteps.map((step, index) => <li key={step.key} className="flex items-center gap-2"><PathCard label={step.label} type={step.type} detail={step.detail} />{index < displaySteps.length - 1 && <PathConnector from={step.type} to={displaySteps[index + 1].type} />}</li>)}
        </ol>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-[#e3c27b] bg-[#fffaf0] p-3 text-sm text-[#536562]"><span className="font-semibold text-[#8a611b]">Break this link:</span> remove the permission that lets the identity enter the next role.</div>
        <div className="rounded-lg border border-[#d4dfdc] bg-white p-3 text-sm text-[#536562]"><span className="font-semibold text-[#314842]">Why it matters:</span> one lower-access identity can become an administrator through connected permissions.</div>
      </div>
      {previewed && (afterPath ? <p className="mt-4 rounded-lg border border-[#e2b7b1] bg-[#fff8f6] p-3 text-sm font-semibold text-[#a33d34]">The route still exists in the preview.</p> : <p className="mt-4 rounded-lg border border-[#b9d7c8] bg-[#f1faf3] p-3 text-sm font-semibold text-[#2c7652]">The route is broken in the preview. Nothing was changed in AWS.</p>)}
    </section>
  );
}

function PathCard({ label, type, detail }: { label: string; type: string; detail: string }) {
  const colors: Record<string, string> = {
    identity: "border-[#c9564c] bg-[#fff3f1]",
    relationship: "border-[#c7d3cf] bg-[#f7faf7]",
    permission: "border-[#e3c27b] bg-[#fffaf0]",
    action: "border-[#e3c27b] bg-[#fffaf0]",
    role: "border-[#b9d7c8] bg-[#f1faf3]",
    impact: "border-[#c9564c] bg-[#fff3f1]",
  };
  return <div className={`w-40 rounded-lg border p-3 ${colors[type] || colors.relationship}`}><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#71817e]">{typeLabel(type)}</p><p className="mt-1 break-words text-sm font-semibold text-[#17252f]">{label}</p><p className="mt-1 break-words text-xs leading-4 text-[#60716e]">{detail}</p></div>;
}

function PathConnector({ from, to }: { from: string; to: string }) {
  return <span className="flex w-24 flex-col items-center gap-1" aria-label={connectionLabel(from, to)}><span className="text-center text-[10px] font-semibold leading-3 text-[#60716e]">{connectionLabel(from, to)}</span><span className="text-lg font-semibold text-[#c9564c]" aria-hidden="true">→</span></span>;
}

function stepType(step: string, index: number, length: number) {
  if (index === 0) return "identity";
  if (index === length - 1) return "role";
  if (step.startsWith("group:")) return "relationship";
  if (step.startsWith("policy:")) return "permission";
  if (step === "sts:AssumeRole") return "action";
  return "role";
}

function stepLabel(step: string, identityMetadata: IdentityMetadata[]) {
  const identity = identityMetadata.find((item) => item.principal_arn === step);
  if (identity) return identity.display_name;
  if (step === "sts:AssumeRole") return "Enter another role";
  if (step.startsWith("group:")) return step.slice("group:".length);
  if (step.startsWith("policy:")) return step.slice("policy:".length);
  return shortName(step);
}

function stepDetail(step: string, person: IdentityMetadata | undefined, index: number, length: number) {
  if (index === 0) return [person?.job_title, person?.department].filter(Boolean).join(" · ") || "Starting identity";
  if (index === length - 1) return "Trusted entry · administrator-level role";
  if (step.startsWith("group:")) return "Team membership";
  if (step.startsWith("policy:")) return "Permission rule";
  if (step === "sts:AssumeRole") return "Allowed capability";
  return "Access role";
}

function connectionLabel(from: string, to: string) {
  if (from === "identity" && to === "relationship") return "belongs to";
  if (from === "identity" && to === "permission") return "has permission";
  if (from === "relationship" && to === "permission") return "grants";
  if (from === "permission" && to === "action") return "allows";
  if (from === "action" && to === "role") return "can enter";
  if (from === "role" && to === "permission") return "has permission";
  if (from === "role" && to === "impact") return "leads to";
  return "connects to";
}

function typeLabel(type: string) {
  return { identity: "Who starts", relationship: "Connection", permission: "Permission rule", action: "Allowed action", role: "Access role", impact: "Impact" }[type] || "Step";
}

function shortName(value: string) {
  if (value.startsWith("arn:")) return value.split("/").pop() || value;
  return value;
}
