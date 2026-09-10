"""Normalize optional authorization sources into graph data for the API/UI."""

from collections.abc import Mapping
from typing import Any


def build_coverage(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Build stable, evidence-carrying nodes and edges from an IAM snapshot."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    edge_ids: set[tuple[str, str, str, str]] = set()
    warnings: list[dict[str, Any]] = []

    def node(node_id: str, kind: str, label: str, source: str) -> str:
        if node_id not in node_ids:
            nodes.append({"id": node_id, "type": kind, "label": label, "source": source})
            node_ids.add(node_id)
        return node_id

    def edge(source: str | None, target: str | None, kind: str, label: str = "", evidence: str = "") -> None:
        if not source or not target or source not in node_ids or target not in node_ids:
            return
        identity = (source, target, kind, label)
        if identity in edge_ids:
            return
        value = {"from": source, "to": target, "type": kind}
        if label:
            value["label"] = label
        if evidence:
            value["evidence"] = evidence
        edges.append(value)
        edge_ids.add(identity)

    users = _records(inventory.get("UserDetailList"))
    groups = _records(inventory.get("GroupDetailList"))
    roles = _records(inventory.get("RoleDetailList"))
    policies = _records(inventory.get("Policies"))

    for item in users:
        node(_principal_id(item), "user", _label(item, "UserName"), "UserDetailList")
    for item in groups:
        node(_principal_id(item, "GroupName"), "group", _label(item, "GroupName"), "GroupDetailList")
    for item in roles:
        node(_principal_id(item, "RoleName"), "role", _label(item, "RoleName"), "RoleDetailList")
    for item in policies:
        node(_policy_id(item), "policy", _label(item, "PolicyName"), "Policies")
    for entity, policy_key in [
        *[(item, "UserPolicyList") for item in users],
        *[(item, "GroupPolicyList") for item in groups],
        *[(item, "RolePolicyList") for item in roles],
    ]:
        for policy in _records(entity.get(policy_key)):
            policy_name = _text(policy.get("PolicyName")) or "inline-policy"
            node(f"policy:{policy_name}", "policy", policy_name, policy_key)

    for user in users:
        user_id = _principal_id(user)
        for group in _values(user.get("GroupList")):
            edge(user_id, _find_id(groups, group, "GroupName"), "member_of", evidence="UserDetailList.GroupList")
        for policy in _values(user.get("AttachedManagedPolicies")) + _records(user.get("UserPolicyList")):
            edge(user_id, _find_policy_id(policies, policy), "grants", evidence="user policy attachment")
    for group in groups:
        group_id = _principal_id(group, "GroupName")
        for member in _records(group.get("Users")) + _values(group.get("Users")):
            edge(_find_id(users, member, "UserName"), group_id, "member_of", evidence="GroupDetailList.Users")
        for policy in _values(group.get("AttachedManagedPolicies")) + _records(group.get("GroupPolicyList")):
            edge(group_id, _find_policy_id(policies, policy), "grants", evidence="group policy attachment")
    for role in roles:
        role_id = _principal_id(role, "RoleName")
        for policy in _values(role.get("AttachedManagedPolicies")) + _records(role.get("RolePolicyList")):
            edge(role_id, _find_policy_id(policies, policy), "grants", evidence="role policy attachment")
        for statement in _statements(role.get("AssumeRolePolicyDocument")):
            for principal in _principal_values(statement.get("Principal")):
                edge(_find_principal_node(principal, users, roles), role_id, "trusts", evidence="AssumeRolePolicyDocument")

    identity_rows = _records(inventory.get("IdentityMetadata"))
    for item in identity_rows:
        principal = _text(item.get("PrincipalArn"))
        if not principal:
            warnings.append({"code": "invalid_identity_metadata", "reason": "PrincipalArn is required"})
            continue
        person_id = _find_principal_node(principal, users, roles)
        if not person_id:
            warnings.append({"code": "unmatched_identity_metadata", "principal": principal})
            continue
        metadata_id = node(
            f"metadata:{item.get('EmployeeId') or principal}",
            "identity_metadata",
            _text(item.get("DisplayName")) or principal,
            "IdentityMetadata",
        )
        metadata.append(_metadata_row(item, principal))
        edge(person_id, metadata_id, "described_by", evidence="IdentityMetadata")

    boundary_count = 0
    for entity, kind, name_key in [*[(item, "user", "UserName") for item in users], *[(item, "role", "RoleName") for item in roles]]:
        boundary = entity.get("PermissionsBoundary")
        if not isinstance(boundary, dict):
            continue
        boundary_arn = _text(boundary.get("PermissionsBoundaryArn"))
        boundary_name = _text(boundary.get("PolicyName")) or boundary_arn or "permissions-boundary"
        boundary_id = node(f"boundary:{boundary_arn or boundary_name}", "boundary", boundary_name, "PermissionsBoundary")
        edge(_principal_id(entity, name_key), boundary_id, "bounded_by", evidence="PermissionsBoundary")
        boundary_count += 1

    resource_rows = _records(inventory.get("ResourcePolicies"))
    for policy in resource_rows:
        resource_arn = _text(policy.get("ResourceArn"))
        policy_name = _text(policy.get("PolicyName")) or resource_arn or "resource-policy"
        policy_id = node(f"resource-policy:{resource_arn}:{policy_name}", "resource_policy", policy_name, "ResourcePolicies")
        resource_id = node(f"resource:{resource_arn}", "resource", resource_arn or "unknown-resource", "ResourcePolicies")
        edge(policy_id, resource_id, "protects", evidence="ResourcePolicies")
        for statement in _statements(policy.get("PolicyDocument")):
            actions = ", ".join(_values(statement.get("Action")))
            for principal in _principal_values(statement.get("Principal")):
                edge(_find_principal_node(principal, users, roles), policy_id, "allowed_by", actions, "ResourcePolicies.PolicyDocument")

    organization = inventory.get("Organizations")
    org_counts = _add_organization(organization, node, edge, warnings)

    session_rows = _records(inventory.get("Sessions"))
    for session in session_rows:
        session_arn = _text(session.get("SessionArn")) or f"session:{len(session_rows)}"
        session_id = node(f"session:{session_arn}", "session", session_arn.rsplit("/", 1)[-1], "Sessions")
        source_value = _text(session.get("SourcePrincipal"))
        source = _find_principal_node(source_value, users, roles)
        if not source and source_value:
            source = node(f"principal:{source_value}", "principal", source_value, "Sessions")
        role_value = _text(session.get("RoleArn"))
        role = _find_principal_node(role_value, users, roles)
        if not role and role_value:
            role = node(f"role:{role_value}", "role", role_value.rsplit("/", 1)[-1], "Sessions")
        edge(source, role, "assumes", evidence="Sessions")
        edge(role, session_id, "has_session", evidence="Sessions")
        if session.get("SessionPolicy") is not None:
            policy_id = node(f"session-policy:{session_arn}", "session_policy", "Session policy", "Sessions")
            edge(session_id, policy_id, "restricted_by", evidence="Sessions.SessionPolicy")

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": metadata,
        "coverage": {
            "identity_metadata": len(metadata),
            "resource_policies": len(resource_rows),
            "boundaries": boundary_count,
            "scp_policies": org_counts["scp_policies"],
            "sessions": len(session_rows),
        },
        "warnings": warnings,
    }


def _add_organization(value: Any, node: Any, edge: Any, warnings: list[dict[str, Any]]) -> dict[str, int]:
    if not isinstance(value, dict):
        return {"scp_policies": 0}
    org_id = _text(value.get("OrganizationId")) or "unknown"
    organization_id = node(f"organization:{org_id}", "organization", org_id, "Organizations")
    root_id = _text(value.get("RootId"))
    if root_id:
        root_node = node(f"root:{root_id}", "root", root_id, "Organizations")
        edge(organization_id, root_node, "contains", evidence="Organizations.RootId")
    for item in _records(value.get("OUs")):
        item_id = _text(item.get("Id"))
        if not item_id:
            warnings.append({"code": "invalid_organization_unit", "reason": "Id is required"})
            continue
        ou_id = node(f"ou:{item_id}", "ou", _text(item.get("Name")) or item_id, "Organizations.OUs")
        parent = _text(item.get("ParentId"))
        edge(f"ou:{parent}" if parent else f"root:{root_id}", ou_id, "contains", evidence="Organizations.OUs")
    for item in _records(value.get("Accounts")):
        account_id = _text(item.get("Id"))
        if not account_id:
            continue
        account_node = node(f"account:{account_id}", "account", _text(item.get("Name")) or account_id, "Organizations.Accounts")
        parent = _text(item.get("ParentId"))
        edge(f"ou:{parent}" if parent else f"root:{root_id}", account_node, "contains", evidence="Organizations.Accounts")
        for identity in [*users_from_account(item), *roles_from_account(item)]:
            edge(account_node, identity, "contains", evidence="Organizations.Accounts")
    scp_rows = _records(value.get("SCPs"))
    for item in scp_rows:
        policy_id = _text(item.get("PolicyArn")) or _text(item.get("PolicyName"))
        if not policy_id:
            continue
        scp_node = node(f"scp:{policy_id}", "scp", _text(item.get("PolicyName")) or policy_id, "Organizations.SCPs")
        for target in _values(item.get("TargetIds")):
            target_id = f"ou:{target}" if target.startswith("ou-") else f"account:{target}"
            edge(scp_node, target_id, "restricts", evidence="Organizations.SCPs")
    return {"scp_policies": len(scp_rows)}


def users_from_account(account: dict[str, Any]) -> list[str]:
    return [f"user:{value}" for value in _values(account.get("UserArns"))]


def roles_from_account(account: dict[str, Any]) -> list[str]:
    return [f"role:{value}" for value in _values(account.get("RoleArns"))]


def _metadata_row(item: dict[str, Any], principal: str) -> dict[str, Any]:
    return {
        "principal_arn": principal,
        "employee_id": _text(item.get("EmployeeId")),
        "display_name": _text(item.get("DisplayName")),
        "job_title": _text(item.get("JobTitle")),
        "department": _text(item.get("Department")),
        "manager": _text(item.get("Manager")),
        "employment_type": _text(item.get("EmploymentType")),
        "status": _text(item.get("Status")),
        "identity_provider": _text(item.get("IdentityProvider")),
    }


def _find_principal_node(value: str | None, users: list[dict[str, Any]], roles: list[dict[str, Any]]) -> str | None:
    if not value:
        return None
    found = _find_id(users, value, "Arn") or _find_id(roles, value, "Arn")
    return found or (value if value.startswith(("user:", "role:")) else None)


def _principal_id(item: dict[str, Any], fallback: str = "UserName") -> str:
    arn = _text(item.get("Arn"))
    return f"{('group:' if fallback == 'GroupName' else 'role:' if fallback == 'RoleName' else 'user:')}{arn or _text(item.get(fallback)) or 'unknown'}"


def _policy_id(item: dict[str, Any]) -> str:
    return f"policy:{_text(item.get('Arn')) or _text(item.get('PolicyArn')) or _text(item.get('PolicyName')) or 'unknown'}"


def _find_policy_id(policies: list[dict[str, Any]], value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    arn = _text(value.get("PolicyArn")) or _text(value.get("Arn"))
    name = _text(value.get("PolicyName"))
    for item in policies:
        if arn and arn in {_text(item.get("Arn")), _text(item.get("PolicyArn"))}:
            return _policy_id(item)
        if name and name == _text(item.get("PolicyName")):
            return _policy_id(item)
    return f"policy:{name or arn}" if name or arn else None


def _find_id(items: list[dict[str, Any]], value: Any, key: str) -> str | None:
    if isinstance(value, dict):
        value = value.get(key) or value.get("Arn") or value.get("UserName") or value.get("GroupName") or value.get("RoleName")
    if not isinstance(value, str):
        return None
    for item in items:
        if value in {_text(item.get(key)), _text(item.get("Arn")), _text(item.get("UserName")), _text(item.get("GroupName")), _text(item.get("RoleName"))}:
            return _principal_id(item, key)
    return None


def _label(item: dict[str, Any], key: str) -> str:
    return _text(item.get(key)) or _text(item.get("Arn")) or "unknown"


def _records(value: Any) -> list[dict[str, Any]]:
    return [item for item in _values(value) if isinstance(item, dict)]


def _values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _statements(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        return []
    value = document.get("Statement", [])
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, dict)]


def _principal_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for key in ("AWS", "Service", "Federated") for item in _values(value.get(key)) if isinstance(item, str)]
    return [item for item in _values(value) if isinstance(item, str)]


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""
