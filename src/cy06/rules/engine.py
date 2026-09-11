"""Evidence-based privilege risk analysis for AWS IAM JSON."""

import fnmatch
import json
from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import unquote

from ..coverage import build_coverage
from ..inventory import InventoryError, summarize_inventory

_USER_MUTATIONS = {"iam:createuser", "iam:deleteuser"}
_POLICY_MUTATIONS = {
    "iam:attachuserpolicy",
    "iam:putuserpolicy",
    "iam:attachrolepolicy",
    "iam:putrolepolicy",
    "iam:updateassumerolepolicy",
}
_SENSITIVE_ACTIONS = _USER_MUTATIONS | _POLICY_MUTATIONS


def analyze_inventory(
    inventory: Mapping[str, Any], context: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Analyze an AWS IAM authorization-details document without changing AWS."""
    if not isinstance(inventory, dict):
        raise InventoryError("inventory must be a JSON object")
    summarize_inventory(inventory)
    context = context or {}
    users = _section(inventory, "UserDetailList")
    groups = _section(inventory, "GroupDetailList")
    roles = _section(inventory, "RoleDetailList")
    policy_docs = _policy_documents(_section(inventory, "Policies"))
    coverage = build_coverage(inventory)
    warnings: list[dict[str, Any]] = []
    warnings.extend(coverage["warnings"])
    findings: list[dict[str, Any]] = []

    group_by_user = _groups_by_user(users, groups)
    role_by_arn: dict[str, dict[str, Any]] = {}
    role_by_name: dict[str, dict[str, Any]] = {}
    for role in roles:
        if isinstance(role.get("Arn"), str):
            role_by_arn[role["Arn"]] = role
        if isinstance(role.get("RoleName"), str):
            role_by_name[role["RoleName"]] = role

    for user in users:
        principal = _identity(user)
        if not principal:
            warnings.append({"code": "unknown_principal", "entity": "user"})
            continue
        statements = _entity_statements(
            user,
            "AttachedManagedPolicies",
            "UserPolicyList",
            policy_docs,
            [principal],
            warnings,
        )
        for group in group_by_user.get(str(user.get("UserName") or ""), []):
            group_name = str(group.get("GroupName") or "unknown-group")
            statements.extend(
                _entity_statements(
                    group,
                    "AttachedManagedPolicies",
                    "GroupPolicyList",
                    policy_docs,
                    [principal, group_name],
                    warnings,
                    via_group=True,
                )
            )

        for statement in statements:
            if statement["unsupported"]:
                _add_warning(warnings, statement["unsupported"], statement["policy"])
                if any(feature != "Condition" for feature in statement["unsupported"]):
                    continue
            for action in statement["actions"]:
                for resource in statement["resources"]:
                    if statement["effect"] != "Allow":
                        continue
                    if _is_denied(statements, action, resource):
                        continue
                    if _is_supplementally_blocked(inventory, user, principal, action, resource, policy_docs):
                        continue
                    confidence = "review_required" if statement["conditions"] else "confirmed"
                    if _is_unrestricted(action) and _is_unrestricted(resource):
                        _add_finding(
                            findings,
                            {
                                "rule_id": "IAM-004",
                                "severity": "critical",
                                "principal": principal,
                                "permission": action,
                                "resource": resource,
                                "path": statement["path"],
                                "reason": "The identity has unrestricted action and resource scope.",
                                "remediation": "Replace wildcard access with required actions and resources.",
                                "confidence": confidence,
                            },
                        )
                        continue
                    if _matches_any(action, _SENSITIVE_ACTIONS):
                        _add_finding(
                            findings,
                            _sensitive_finding(principal, action, resource, statement, confidence),
                        )
                    if _matches(action, "sts:AssumeRole"):
                        _add_assume_role_findings(
                            findings,
                            principal,
                            resource,
                            statement,
                            confidence,
                            role_by_arn,
                            role_by_name,
                            warnings,
                        )

    approved = context.get("approved_admins", [])
    if approved and not isinstance(approved, list):
        warnings.append({"code": "invalid_context", "field": "approved_admins"})
    for role in roles:
        if role.get("PermissionsBoundary") and not isinstance(role["PermissionsBoundary"], dict):
            warnings.append({"code": "review_required", "feature": "PermissionsBoundary"})
    for session in _section(inventory, "Sessions"):
        if "SessionPolicy" not in session:
            warnings.append({"code": "review_required", "feature": "SessionPolicy", "reason": "session policy was not supplied"})

    paths = _find_privilege_paths(
        users,
        group_by_user,
        role_by_arn,
        role_by_name,
        policy_docs,
        inventory,
        warnings,
    )
    findings.sort(key=lambda item: (0 if item["severity"] == "critical" else 1, item["principal"], item["permission"], item["path"]))
    critical = sum(item["severity"] == "critical" for item in findings) + sum(
        item["risk"] == "critical" for item in paths
    )
    high = sum(item["severity"] == "high" for item in findings) + sum(
        item["risk"] == "high" for item in paths
    )
    return {
        "status": "ok",
        "summary": {
            "findings": len(findings),
            "paths": len(paths),
            "critical": critical,
            "high": high,
        },
        "findings": findings,
        "warnings": _dedupe_warnings(warnings),
        "graph": {"nodes": coverage["nodes"], "edges": coverage["edges"]},
        "coverage": coverage["coverage"],
        "identity_metadata": coverage["metadata"],
        "paths": paths,
    }


def _find_privilege_paths(
    users: list[dict[str, Any]],
    group_by_user: dict[str, list[dict[str, Any]]],
    role_by_arn: dict[str, dict[str, Any]],
    role_by_name: dict[str, dict[str, Any]],
    policy_docs: dict[str, dict[str, Any]],
    inventory: Mapping[str, Any],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    for user in users:
        principal = _identity(user)
        if not principal:
            continue
        starting_privilege = _starting_privilege(
            user,
            principal,
            group_by_user,
            policy_docs,
            inventory,
            warnings,
        )
        queue = deque([(principal, user, [principal], 0, set(), False)])
        while queue:
            current_principal, entity, current_path, hops, visited, path_requires_review = queue.popleft()
            statements = _effective_path_statements(
                entity,
                current_principal,
                group_by_user,
                policy_docs,
                warnings,
            )
            for statement in statements:
                if statement["effect"] != "Allow" or not _matches_any("sts:AssumeRole", statement["actions"]):
                    continue
                for resource in statement["resources"]:
                    if _is_denied(statements, "sts:AssumeRole", resource):
                        continue
                    if _is_supplementally_blocked(inventory, entity, current_principal, "sts:AssumeRole", resource, policy_docs):
                        continue
                    targets = _role_targets(resource, role_by_arn, role_by_name)
                    for target in targets:
                        target_arn = str(target.get("Arn") or "")
                        trust_allows, conditional_trust = _trust_allows(target, current_principal)
                        if not target_arn or target_arn in visited or not trust_allows:
                            continue
                        role_name = str(target.get("RoleName") or target_arn)
                        if conditional_trust:
                            _add_trust_condition_warning(warnings, role_name)
                        next_path = current_path + _statement_tail(statement) + ["sts:AssumeRole", role_name]
                        next_hops = hops + 1
                        next_requires_review = path_requires_review or statement["conditions"] or conditional_trust
                        if _is_privileged_role(target, warnings):
                            paths.append(
                                _privilege_path(
                                    principal,
                                    target_arn,
                                    next_path,
                                    next_hops,
                                    resource,
                                    statement,
                                    starting_privilege,
                                    next_requires_review,
                                )
                            )
                        else:
                            queue.append((target_arn, target, next_path, next_hops, visited | {target_arn}, next_requires_review))
    unique = {tuple(item["path"]): item for item in paths}
    return sorted(unique.values(), key=lambda item: (-item["risk_score"], item["path"]))


def _effective_path_statements(
    entity: dict[str, Any],
    principal: str,
    group_by_user: dict[str, list[dict[str, Any]]],
    policy_docs: dict[str, dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if principal.startswith("arn:aws:iam::") and ":user/" in principal:
        statements = _entity_statements(entity, "AttachedManagedPolicies", "UserPolicyList", policy_docs, [principal], warnings)
        for group in group_by_user.get(str(entity.get("UserName") or ""), []):
            statements.extend(
                _entity_statements(
                    group,
                    "AttachedManagedPolicies",
                    "GroupPolicyList",
                    policy_docs,
                    [principal, str(group.get("GroupName") or "unknown-group")],
                    warnings,
                    via_group=True,
                )
            )
        return statements
    return _entity_statements(entity, "AttachedManagedPolicies", "RolePolicyList", policy_docs, [str(entity.get("RoleName") or principal)], warnings)


def _statement_tail(statement: dict[str, Any]) -> list[str]:
    path = list(statement["path"])
    if statement["via_group"] and len(path) > 1:
        path[1] = f"group:{path[1]}"
    return path[1:] if path else []


def _role_targets(resource: str, role_by_arn: dict[str, dict[str, Any]], role_by_name: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if resource == "*":
        return list(role_by_arn.values())
    if resource in role_by_arn:
        return [role_by_arn[resource]]
    role = role_by_name.get(resource.rsplit("/", 1)[-1])
    return [role] if role else []


def _privilege_path(
    principal: str,
    target: str,
    path: list[str],
    hops: int,
    resource: str,
    statement: dict[str, Any],
    starting_privilege: str,
    requires_review: bool,
) -> dict[str, Any]:
    confirmed = not requires_review
    score_breakdown = {
        "target_impact": 40,
        "assumption_resource_breadth": 20 if resource == "*" else 10,
        "hop_directness": max(5, 30 - (hops - 1) * 5),
        "source_context": 5 if starting_privilege == "low" else 0,
        "confidence": 5 if confirmed else 0,
    }
    risk_score = min(100, sum(score_breakdown.values()))
    return {
        "principal": principal,
        "target": target,
        "risk": "critical" if risk_score >= 80 else "high",
        "risk_score": risk_score,
        "score_breakdown": score_breakdown,
        "starting_privilege": starting_privilege,
        "hops": hops,
        "path": path,
        "permission": "sts:AssumeRole",
        "reason": "The identity can reach administrator-level access through chained role assumptions.",
        "remediation": {
            "policy_name": statement["policy"],
            "statement_index": statement["statement_index"],
            "action": "sts:AssumeRole",
            "resource": resource,
        },
        "confidence": "confirmed" if confirmed else "review_required",
    }


def _starting_privilege(
    user: dict[str, Any],
    principal: str,
    group_by_user: dict[str, list[dict[str, Any]]],
    policy_docs: dict[str, dict[str, Any]],
    inventory: Mapping[str, Any],
    warnings: list[dict[str, Any]],
) -> str:
    groups = group_by_user.get(str(user.get("UserName") or ""), [])
    if any(_has_administrator_policy(entity) for entity in [user, *groups]):
        return "elevated"

    statements = _effective_path_statements(
        user, principal, group_by_user, policy_docs, warnings
    )
    for statement in statements:
        if statement["effect"] != "Allow":
            continue
        for action in statement["actions"]:
            for resource in statement["resources"]:
                if _is_denied(statements, action, resource):
                    continue
                if _is_supplementally_blocked(
                    inventory, user, principal, action, resource, policy_docs
                ):
                    continue
                sensitive = any(_matches(action, value) for value in _SENSITIVE_ACTIONS)
                if sensitive or (_is_unrestricted(action) and _is_unrestricted(resource)):
                    return "elevated"
    return "low"


def _has_administrator_policy(entity: dict[str, Any]) -> bool:
    return any(
        isinstance(policy, dict)
        and str(policy.get("PolicyName", "")).casefold() == "administratoraccess"
        for policy in entity.get("AttachedManagedPolicies", [])
    )


def _sensitive_finding(
    principal: str,
    action: str,
    resource: str,
    statement: dict[str, Any],
    confidence: str,
) -> dict[str, Any]:
    via_group = statement["via_group"]
    if via_group:
        rule_id = "IAM-003"
        reason = "A group grants a sensitive IAM permission to its members."
        remediation = "Remove the sensitive action from the group policy or narrow its resource scope."
    elif action.casefold() in _USER_MUTATIONS:
        rule_id = "IAM-001"
        reason = "The identity can create or delete IAM users."
        remediation = "Remove the IAM user-management action unless it is required."
    else:
        rule_id = "IAM-002"
        reason = "The identity can change IAM permissions or role trust."
        remediation = "Remove the policy-management action unless it is required."
    return {
        "rule_id": rule_id,
        "severity": "critical" if action.casefold() in _USER_MUTATIONS else "high",
        "principal": principal,
        "permission": action,
        "resource": resource,
        "path": statement["path"] + [action],
        "reason": reason,
        "remediation": remediation,
        "confidence": confidence,
    }


def _add_assume_role_findings(
    findings: list[dict[str, Any]],
    principal: str,
    resource: str,
    statement: dict[str, Any],
    confidence: str,
    role_by_arn: dict[str, dict[str, Any]],
    role_by_name: dict[str, dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    targets = []
    if resource == "*":
        targets = list(role_by_arn.values())
    elif resource in role_by_arn:
        targets = [role_by_arn[resource]]
    else:
        role_name = resource.rsplit("/", 1)[-1]
        if role_name in role_by_name:
            targets = [role_by_name[role_name]]
    for role in targets:
        if not _is_privileged_role(role, warnings):
            continue
        trust_allows, conditional_trust = _trust_allows(role, principal)
        if not trust_allows:
            continue
        role_name = role.get("RoleName") or role.get("Arn") or "unknown-role"
        if conditional_trust:
            _add_trust_condition_warning(warnings, str(role_name))
        _add_finding(
            findings,
            {
                "rule_id": "IAM-005",
                "severity": "critical",
                "principal": principal,
                "permission": "sts:AssumeRole",
                "resource": role.get("Arn", resource),
                "path": statement["path"] + ["sts:AssumeRole", str(role_name), "privileged-policy"],
                "reason": "The identity can assume a role with administrator-level permissions.",
                "remediation": "Remove the role-assumption permission or reduce the target role's privileges.",
                "confidence": "review_required" if conditional_trust else confidence,
            },
        )


def _is_privileged_role(role: dict[str, Any], warnings: list[dict[str, Any]]) -> bool:
    attached = role.get("AttachedManagedPolicies", [])
    if any(
        isinstance(policy, dict)
        and str(policy.get("PolicyName", "")).casefold() == "administratoraccess"
        for policy in attached
    ):
        return True
    statements = _entity_statements(
        role,
        "AttachedManagedPolicies",
        "RolePolicyList",
        {},
        [str(role.get("RoleName") or role.get("Arn") or "role")],
        warnings,
    )
    return any(
        statement["effect"] == "Allow"
        and any(_is_unrestricted(action) for action in statement["actions"])
        and any(_is_unrestricted(resource) for resource in statement["resources"])
        for statement in statements
    )


def _trust_allows(role: dict[str, Any], principal: str) -> tuple[bool, bool]:
    document = _document(role.get("AssumeRolePolicyDocument"))
    if not document:
        return False, False
    conditional_match = False
    for statement in _statements(document):
        if statement.get("Effect") != "Allow":
            continue
        if not _matches_any("sts:AssumeRole", _values(statement.get("Action"))):
            continue
        principal_value = statement.get("Principal", {})
        principals = principal_value.get("AWS", []) if isinstance(principal_value, dict) else principal_value
        account = _account_id(principal)
        matches = (
            "*" in _values(principals)
            or principal in _values(principals)
            or bool(account and f"arn:aws:iam::{account}:root" in _values(principals))
        )
        if not matches:
            continue
        if statement.get("Condition"):
            conditional_match = True
            continue
        return True, False
    return conditional_match, conditional_match


def _add_trust_condition_warning(warnings: list[dict[str, Any]], role: str) -> None:
    warnings.append(
        {
            "code": "review_required",
            "feature": "TrustPolicyCondition",
            "role": role,
        }
    )


def _entity_statements(
    entity: dict[str, Any],
    managed_key: str,
    inline_key: str,
    policy_docs: dict[str, dict[str, Any]],
    path_prefix: list[str],
    warnings: list[dict[str, Any]],
    via_group: bool = False,
) -> list[dict[str, Any]]:
    references: list[tuple[str, Any]] = []
    for inline in entity.get(inline_key, []):
        if isinstance(inline, dict):
            references.append((str(inline.get("PolicyName") or "inline-policy"), inline.get("PolicyDocument")))
    for attached in entity.get(managed_key, []):
        if not isinstance(attached, dict):
            continue
        label = str(attached.get("PolicyName") or attached.get("PolicyArn") or "managed-policy")
        document = policy_docs.get(str(attached.get("PolicyArn"))) or policy_docs.get(label)
        if document is None and label.casefold() != "administratoraccess":
            _add_warning(warnings, ["MissingPolicyDocument"], label)
        references.append((label, document))

    result = []
    for policy, raw_document in references:
        document = _document(raw_document)
        if not document:
            continue
        raw_statements = document.get("Statement", [])
        raw_statements = raw_statements if isinstance(raw_statements, list) else [raw_statements]
        for statement_index, statement in enumerate(raw_statements):
            if not isinstance(statement, dict):
                continue
            unsupported = []
            if "NotAction" in statement:
                unsupported.append("NotAction")
            if "NotResource" in statement:
                unsupported.append("NotResource")
            if "Condition" in statement:
                unsupported.append("Condition")
            result.append(
                {
                    "effect": str(statement.get("Effect", "Deny")),
                    "actions": _values(statement.get("Action")),
                    "resources": _values(statement.get("Resource")) or ["*"],
                    "policy": policy,
                    "path": path_prefix + [f"policy:{policy}"],
                    "conditions": bool(statement.get("Condition")),
                    "statement_index": statement_index,
                    "unsupported": unsupported,
                    "via_group": via_group,
                }
            )
    return result


def _policy_documents(policies: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for policy in policies:
        raw = policy.get("PolicyDocument")
        if raw is None:
            for version in policy.get("PolicyVersionList", []):
                if version.get("IsDefaultVersion") or version.get("VersionId") == policy.get("DefaultVersionId"):
                    raw = version.get("Document")
                    break
        document = _document(raw)
        if document:
            for key in (policy.get("Arn"), policy.get("PolicyArn"), policy.get("PolicyName")):
                if key:
                    documents[str(key)] = document
    return documents


def _document(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(unquote(raw))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _statements(document: Any) -> list[dict[str, Any]]:
    value = document.get("Statement", [])
    values = [value] if isinstance(value, dict) else value
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def _section(inventory: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    value = inventory.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise InventoryError(f"{name} must be a list of objects")
    return value


def _identity(entity: dict[str, Any]) -> str:
    return str(entity.get("Arn") or entity.get("UserName") or "")


def _groups_by_user(
    users: Iterable[dict[str, Any]], groups: Iterable[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    groups = list(groups)
    by_name = {str(group.get("GroupName")): group for group in groups}
    result: dict[str, list[dict[str, Any]]] = {}
    for user in users:
        user_name = str(user.get("UserName") or "")
        for group_name in user.get("GroupList", []):
            group = by_name.get(str(group_name))
            if user_name and group:
                result.setdefault(user_name, []).append(group)
    for group in groups:
        for member in group.get("Users", []):
            user_name = member.get("UserName") if isinstance(member, dict) else member
            if user_name and group not in result.get(str(user_name), []):
                result.setdefault(str(user_name), []).append(group)
    return result


def _values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    return []


def _matches(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value.casefold(), pattern.casefold())


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(_matches(pattern, value) for pattern in patterns)


def _is_unrestricted(value: str) -> bool:
    return value == "*"


def _is_denied(statements: Iterable[dict[str, Any]], action: str, resource: str) -> bool:
    return any(
        statement["effect"] == "Deny"
        and not statement["unsupported"]
        and _matches_any(action, statement["actions"])
        and _matches_any(resource, statement["resources"])
        for statement in statements
    )


def _is_supplementally_blocked(
    inventory: Mapping[str, Any],
    entity: dict[str, Any],
    principal: str,
    action: str,
    resource: str,
    policy_docs: dict[str, dict[str, Any]],
) -> bool:
    boundary = entity.get("PermissionsBoundary")
    if isinstance(boundary, dict):
        document = _document(boundary.get("PolicyDocument"))
        if document is None:
            reference = str(boundary.get("PermissionsBoundaryArn") or boundary.get("PolicyName") or "")
            document = policy_docs.get(reference)
        if document and not _document_allows(document, action, resource):
            return True
    if _resource_policy_denies(inventory, principal, action, resource):
        return True
    return _scp_denies(inventory, principal, action, resource)


def _document_allows(document: dict[str, Any], action: str, resource: str) -> bool:
    statements = _statements(document)
    if any(
        statement.get("Effect") == "Deny"
        and _matches_any(action, _values(statement.get("Action")))
        and _matches_any(resource, _values(statement.get("Resource")) or ["*"])
        for statement in statements
    ):
        return False
    return any(
        statement.get("Effect") == "Allow"
        and "Condition" not in statement
        and _matches_any(action, _values(statement.get("Action")))
        and _matches_any(resource, _values(statement.get("Resource")) or ["*"])
        for statement in statements
    )


def _resource_policy_denies(inventory: Mapping[str, Any], principal: str, action: str, resource: str) -> bool:
    for policy in _section(inventory, "ResourcePolicies"):
        for statement in _statements(policy.get("PolicyDocument")):
            if statement.get("Effect") != "Deny":
                continue
            principals = _values(statement.get("Principal"))
            if isinstance(statement.get("Principal"), dict):
                principals = [item for key in ("AWS", "Service", "Federated") for item in _values(statement["Principal"].get(key))]
            if ("*" in principals or principal in principals) and _matches_any(action, _values(statement.get("Action"))) and _matches_any(resource, _values(statement.get("Resource")) or ["*"]):
                return True
    return False


def _scp_denies(inventory: Mapping[str, Any], principal: str, action: str, resource: str) -> bool:
    organization = inventory.get("Organizations")
    if not isinstance(organization, dict):
        return False
    account = _account_id(principal)
    if not account:
        return False
    targets = {account}
    parents = {str(item.get("Id")): str(item.get("ParentId")) for item in _section_like(organization.get("Accounts")) if item.get("Id") and item.get("ParentId")}
    parents.update({str(item.get("Id")): str(item.get("ParentId")) for item in _section_like(organization.get("OUs")) if item.get("Id") and item.get("ParentId")})
    current = account
    while current in parents:
        current = parents[current]
        targets.add(current)
    for policy in _section_like(organization.get("SCPs")):
        if not targets.intersection(_values(policy.get("TargetIds"))):
            continue
        for statement in _statements(policy.get("PolicyDocument")):
            if statement.get("Effect") == "Deny" and _matches_any(action, _values(statement.get("Action"))) and _matches_any(resource, _values(statement.get("Resource")) or ["*"]):
                return True
    return False


def _section_like(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _account_id(arn: str) -> str:
    parts = arn.split(":")
    return parts[4] if len(parts) > 4 and parts[4].isdigit() else ""


def _add_finding(findings: list[dict[str, Any]], finding: dict[str, Any]) -> None:
    identity = (finding["rule_id"], finding["principal"], finding["permission"], tuple(finding["path"]))
    if not any((item["rule_id"], item["principal"], item["permission"], tuple(item["path"])) == identity for item in findings):
        findings.append(finding)


def _add_warning(warnings: list[dict[str, Any]], features: list[str], policy: str) -> None:
    for feature in features:
        warnings.append({"code": "review_required", "feature": feature, "policy": policy})


def _dedupe_warnings(warnings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for warning in warnings:
        if warning not in result:
            result.append(warning)
    return result
