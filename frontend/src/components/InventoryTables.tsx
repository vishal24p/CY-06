import type { IdentityMetadata, Inventory } from "@/lib/types";

export function InventoryTables({ inventory, identityMetadata }: { inventory: Inventory; identityMetadata: IdentityMetadata[] }) {
  const users = records(inventory.UserDetailList);
  const groups = records(inventory.GroupDetailList);
  const roles = records(inventory.RoleDetailList);
  const policies = records(inventory.Policies);
  const resources = records(inventory.ResourcePolicies);
  const sessions = records(inventory.Sessions);
  const scps = isRecord(inventory.Organizations) ? records(inventory.Organizations.SCPs) : [];
  const boundaries = [...users, ...roles].flatMap((entity) => isRecord(entity.PermissionsBoundary) ? [[text(entity.UserName ?? entity.RoleName), text(entity.PermissionsBoundary.PolicyName ?? entity.PermissionsBoundary.PermissionsBoundaryArn)]] : []);
  return (
    <section className="space-y-5" aria-labelledby="tables-heading">
      <div><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Source inventory</p><h2 id="tables-heading" className="mt-1 text-xl font-semibold text-[#17252f]">IAM tables</h2></div>
      <DataTable title="Users" columns={["User", "ARN", "Groups", "Policies"]} rows={users.map((user) => [text(user.UserName), text(user.Arn), list(user.GroupList), list([...array(user.AttachedManagedPolicies), ...array(user.UserPolicyList)], "PolicyName")])} />
      <DataTable title="Groups" columns={["Group", "ARN", "Members", "Policies"]} rows={groups.map((group) => [text(group.GroupName), text(group.Arn), list(group.Users, "UserName"), list([...array(group.AttachedManagedPolicies), ...array(group.GroupPolicyList)], "PolicyName")])} />
      <DataTable title="Roles" columns={["Role", "ARN", "Trusted principals", "Policies"]} rows={roles.map((role) => [text(role.RoleName), text(role.Arn), trusted(role.AssumeRolePolicyDocument), list([...array(role.AttachedManagedPolicies), ...array(role.RolePolicyList)], "PolicyName")])} />
      <DataTable title="Policies" columns={["Policy", "ARN", "Attachments"]} rows={policies.map((policy) => [text(policy.PolicyName), text(policy.Arn), text(policy.AttachmentCount)])} />
      <div className="border-t border-[#cad6d2] pt-5"><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Supplemental authorization sources</p><p className="mt-1 text-sm text-[#71817e]">These records refine effective access; they are not inferred from usernames.</p></div>
      <DataTable title="HR / IdP metadata" columns={["Person", "Job title", "Department", "Status", "Provider"]} rows={identityMetadata.map((item) => [item.display_name, item.job_title, item.department, item.status, item.identity_provider])} />
      <DataTable title="Resource policies" columns={["Policy", "Resource", "Policy ARN"]} rows={resources.map((item) => [text(item.PolicyName), text(item.ResourceArn), text(item.PolicyArn)])} />
      <DataTable title="Organizations SCPs" columns={["SCP", "Targets", "Policy ARN"]} rows={scps.map((item) => [text(item.PolicyName), list(item.TargetIds), text(item.PolicyArn)])} />
      <DataTable title="Sessions" columns={["Session", "Source principal", "Role", "Session policy"]} rows={sessions.map((item) => [text(item.SessionArn), text(item.SourcePrincipal), text(item.RoleArn), isRecord(item.SessionPolicy) ? "present" : "missing — review required"])} />
      <DataTable title="Permissions boundaries" columns={["Principal", "Boundary"]} rows={boundaries} />
    </section>
  );
}

function DataTable({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return <div className="overflow-hidden rounded-xl border border-[#d4dfdc] bg-white"><div className="border-b border-[#dce5e1] px-5 py-3"><h3 className="font-semibold text-[#17252f]">{title} <span className="ml-2 font-mono text-xs text-[#71817e]">{rows.length}</span></h3></div><div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><caption className="sr-only">{title} IAM records</caption><thead className="bg-[#f3f7f4] text-xs uppercase tracking-wider text-[#60716e]"><tr>{columns.map((column) => <th key={column} scope="col" className="whitespace-nowrap px-5 py-3">{column}</th>)}</tr></thead><tbody className="divide-y divide-[#e3ebe7]">{rows.length ? rows.map((row, rowIndex) => <tr key={`${title}-${rowIndex}`} className="hover:bg-[#f6faf7]">{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`} className="max-w-[360px] whitespace-normal break-all px-5 py-3 align-top font-mono text-xs text-[#536562]">{cell || "—"}</td>)}</tr>) : <tr><td colSpan={columns.length} className="px-5 py-5 text-sm text-[#71817e]">No records in uploaded inventory.</td></tr>}</tbody></table></div></div>;
}

function records(value: unknown) { return Array.isArray(value) ? value.filter(isRecord) : []; }
function array(value: unknown) { return Array.isArray(value) ? value : []; }
function text(value: unknown) { return typeof value === "string" || typeof value === "number" ? String(value) : ""; }
function list(value: unknown, name?: string) { return array(value).map((item) => isRecord(item) ? text(item[name ?? "Name"] ?? item.Arn ?? item.UserName) : text(item)).filter(Boolean).join(", "); }
function trusted(value: unknown) { if (!isRecord(value)) return ""; return array(value.Statement).flatMap((statement) => isRecord(statement) && isRecord(statement.Principal) ? [statement.Principal.AWS] : []).map(text).filter(Boolean).join(", "); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
