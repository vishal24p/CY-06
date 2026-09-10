"""Load and summarize AWS IAM authorization-details JSON."""

import json
from pathlib import Path
from typing import Any


class InventoryError(ValueError):
    """Raised when a local IAM inventory cannot be read or validated."""


_SECTIONS = ("UserDetailList", "GroupDetailList", "RoleDetailList", "Policies")


def load_inventory(path: str | Path) -> dict[str, Any]:
    """Read an AWS IAM authorization-details JSON document."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InventoryError("input file not found") from error
    except json.JSONDecodeError as error:
        raise InventoryError("invalid JSON") from error
    except OSError as error:
        raise InventoryError("cannot read input file") from error

    if not isinstance(payload, dict):
        raise InventoryError("top-level JSON must be an object")
    for section in _SECTIONS:
        _section(payload, section)
    return payload


def summarize_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    """Return safe counts for an already-loaded IAM inventory."""
    users = _section(payload, "UserDetailList")
    groups = _section(payload, "GroupDetailList")
    roles = _section(payload, "RoleDetailList")
    policies = _section(payload, "Policies")

    relationships = sum(
        _nested_count(user, "GroupList")
        + _nested_count(user, "AttachedManagedPolicies")
        + _nested_count(user, "UserPolicyList")
        for user in users
    )
    relationships += sum(
        _nested_count(group, "Users")
        + _nested_count(group, "AttachedManagedPolicies")
        + _nested_count(group, "GroupPolicyList")
        for group in groups
    )
    relationships += sum(
        _nested_count(role, "AttachedManagedPolicies")
        + _nested_count(role, "RolePolicyList")
        + _nested_count(role, "InstanceProfileList")
        + _trust_count(role)
        for role in roles
    )

    return {
        "status": "ok",
        "users": len(users),
        "groups": len(groups),
        "roles": len(roles),
        "policies": len(policies),
        "relationships": relationships,
        "warnings": [],
    }


def _section(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = payload.get(name, [])
    if not isinstance(value, list):
        raise InventoryError(f"{name} must be a list")
    if not all(isinstance(item, dict) for item in value):
        raise InventoryError(f"{name} must contain objects")
    return value


def _nested_count(item: dict[str, Any], name: str) -> int:
    value = item.get(name, [])
    if not isinstance(value, list):
        raise InventoryError(f"{name} must be a list")
    return len(value)


def _trust_count(role: dict[str, Any]) -> int:
    document = role.get("AssumeRolePolicyDocument", {})
    if not isinstance(document, dict):
        return 0
    statements = document.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        raise InventoryError("Statement must be a list or object")
    return sum(
        bool(
            isinstance(statement, dict)
            and statement.get("Effect") == "Allow"
            and statement.get("Principal")
            and statement.get("Action")
        )
        for statement in statements
    )
