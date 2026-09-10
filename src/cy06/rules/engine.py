"""Evidence-based privilege risk analysis for AWS IAM JSON."""

import fnmatch
import json
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import unquote

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
    warnings: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    group_by_user = _groups_by_user(groups)
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
                    confidence = "review_required" if statement["conditions"] else "confirmed"
                    if _is_wildcard(action) and _is_wildcard(resource):
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
        if role.get("PermissionsBoundary"):
            warnings.append({"code": "review_required", "feature": "PermissionsBoundary"})

    critical = sum(item["severity"] == "critical" for item in findings)
    high = sum(item["severity"] == "high" for item in findings)
    return {
        "status": "ok",
        "summary": {"findings": len(findings), "critical": critical, "high": high},
        "findings": findings,
        "warnings": _dedupe_warnings(warnings),
    }


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
        if not _trust_allows(role, principal):
            continue
        role_name = role.get("RoleName") or role.get("Arn") or "unknown-role"
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
                "confidence": confidence,
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
        and any(_is_wildcard(action) for action in statement["actions"])
        and any(_is_wildcard(resource) for resource in statement["resources"])
        for statement in statements
    )


def _trust_allows(role: dict[str, Any], principal: str) -> bool:
    document = _document(role.get("AssumeRolePolicyDocument"))
    if not document:
        return False
    for statement in _statements(document):
        if statement.get("Effect") != "Allow":
            continue
        if not _matches_any("sts:AssumeRole", _values(statement.get("Action"))):
            continue
        principal_value = statement.get("Principal", {})
        principals = principal_value.get("AWS", []) if isinstance(principal_value, dict) else principal_value
        if "*" in _values(principals) or principal in _values(principals):
            return True
        account = _account_id(principal)
        if account and f"arn:aws:iam::{account}:root" in _values(principals):
            return True
    return False


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
        for statement in _statements(document):
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


def _statements(document: dict[str, Any]) -> list[dict[str, Any]]:
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


def _groups_by_user(groups: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        for member in group.get("Users", []):
            user_name = member.get("UserName") if isinstance(member, dict) else member
            if user_name:
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


def _is_wildcard(value: str) -> bool:
    return value == "*" or "*" in value


def _is_denied(statements: Iterable[dict[str, Any]], action: str, resource: str) -> bool:
    return any(
        statement["effect"] == "Deny"
        and not statement["unsupported"]
        and _matches_any(action, statement["actions"])
        and _matches_any(resource, statement["resources"])
        for statement in statements
    )


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
