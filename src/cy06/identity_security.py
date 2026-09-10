"""Local PostgreSQL tools for evidence-backed identity-security work."""

from __future__ import annotations

import copy
import json
import os
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from .rules import analyze_inventory

APPROVAL_PHRASE = "Approve this change"
_OPERATIONS = {
    "remove_user_policy",
    "remove_group_membership",
    "detach_policy",
    "remove_role_relationship",
    "update_policy_statement",
    "update_trust_relationship",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_state (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS identity_entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS identity_entities_type_name ON identity_entities (entity_type, name);
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY REFERENCES identity_entities(entity_id) ON DELETE CASCADE,
    policy_document JSONB,
    document_available BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES identity_entities(entity_id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES identity_entities(entity_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    evidence JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS relationships_source_target ON relationships (source_id, target_id);
CREATE TABLE IF NOT EXISTS privilege_paths (
    path_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    risk TEXT NOT NULL,
    evidence JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS security_findings (
    finding_id TEXT PRIMARY KEY,
    path_id TEXT REFERENCES privilege_paths(path_id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    risk TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    evidence JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS remediation_plans (
    plan_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    change JSONB NOT NULL,
    before_document JSONB NOT NULL,
    after_document JSONB NOT NULL,
    simulation JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id TEXT PRIMARY KEY,
    plan_id TEXT REFERENCES remediation_plans(plan_id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class IdentitySecurityError(ValueError):
    """A safe, actionable local identity-security error."""


class IdentitySecurityTools:
    """Small non-overlapping tool surface backed only by local PostgreSQL."""

    def __init__(
        self,
        database_url: str | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._database_url = database_url or os.environ.get("CY06_DATABASE_URL")
        self._connection_factory = connection_factory

    def initialize(self) -> None:
        """Create the fixed local schema. No caller-provided SQL is accepted."""
        with self._connection(write=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(_SCHEMA)

    def import_inventory(self, inventory: Mapping[str, Any]) -> dict[str, int]:
        """Replace the active local import and rebuild its evidence indexes."""
        document = _copy_document(inventory)
        with self._connection(write=True) as connection:
            with connection.cursor() as cursor:
                self._write_state(cursor, document)
                counts = self._rebuild(cursor, document)
                self._write_audit(cursor, None, "import_inventory", "completed", {"counts": counts})
        return counts

    def list_postgres_tables(self) -> list[str]:
        return [row["table_name"] for row in self._query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() ORDER BY table_name"
        )]

    def list_identity_entities(
        self,
        *,
        search: str | None = None,
        entity_type: str | None = None,
        sort_by: str = "name",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        order_by = {"name": "name", "type": "entity_type"}.get(sort_by)
        if not order_by:
            raise IdentitySecurityError("sort_by must be name or type")
        return self._query(
            "SELECT entity_id, entity_type, name, data FROM identity_entities "
            "WHERE (%s IS NULL OR entity_type = %s) "
            "AND (%s IS NULL OR name ILIKE %s) "
            f"ORDER BY {order_by}, entity_id LIMIT %s OFFSET %s",
            (entity_type, entity_type, search, f"%{search}%" if search else None, _limit(limit), _offset(offset)),
        )

    def get_identity_entity(self, entity_id: str) -> dict[str, Any]:
        entity = self._one(
            "SELECT entity_id, entity_type, name, data FROM identity_entities WHERE entity_id = %s",
            (entity_id,),
        )
        if not entity:
            raise IdentitySecurityError("identity entity not found")
        entity["relationships"] = self._query(
            "SELECT relationship_id, source_id, target_id, relationship_type, evidence FROM relationships "
            "WHERE source_id = %s OR target_id = %s ORDER BY relationship_type",
            (entity_id, entity_id),
        )
        entity["related_privilege_paths"] = self._query(
            "SELECT path_id, principal_id, target_id, risk, evidence FROM privilege_paths "
            "WHERE principal_id = %s OR target_id = %s ORDER BY risk DESC",
            (entity_id, entity_id),
        )
        entity["effective_permissions"] = self._query(
            "SELECT p.policy_id, p.policy_document, p.document_available FROM policies p "
            "JOIN relationships r ON r.target_id = p.policy_id "
            "WHERE r.source_id = %s AND r.relationship_type = 'attached_policy'",
            (entity_id,),
        )
        return entity

    def list_privilege_paths(self, *, risk: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self._query(
            "SELECT path_id, principal_id, target_id, risk, evidence FROM privilege_paths "
            "WHERE (%s IS NULL OR risk = %s) ORDER BY risk DESC, path_id LIMIT %s OFFSET %s",
            (risk, risk, _limit(limit), _offset(offset)),
        )

    def get_privilege_path(self, path_id: str) -> dict[str, Any]:
        path = self._one(
            "SELECT path_id, principal_id, target_id, risk, evidence FROM privilege_paths WHERE path_id = %s",
            (path_id,),
        )
        if not path:
            raise IdentitySecurityError("privilege path not found")
        return path

    def list_security_findings(self, *, status: str | None = None, risk: str | None = None) -> list[dict[str, Any]]:
        return self._query(
            "SELECT finding_id, path_id, title, risk, status, evidence FROM security_findings "
            "WHERE (%s IS NULL OR status = %s) AND (%s IS NULL OR risk = %s) "
            "ORDER BY risk DESC, finding_id",
            (status, status, risk, risk),
        )

    def list_remediation_plans(self, *, status: str | None = None) -> list[dict[str, Any]]:
        return self._query(
            "SELECT plan_id, status, change, simulation, created_at, completed_at FROM remediation_plans "
            "WHERE (%s IS NULL OR status = %s) ORDER BY created_at DESC",
            (status, status),
        )

    def list_audit_logs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._query(
            "SELECT audit_id, plan_id, action, status, details, created_at FROM audit_logs "
            "ORDER BY created_at DESC LIMIT %s",
            (_limit(limit),),
        )

    def analyze_policy_impact(self, policy_id: str) -> dict[str, Any]:
        policy = self._one(
            "SELECT p.policy_id, e.name, p.policy_document, p.document_available FROM policies p "
            "JOIN identity_entities e ON e.entity_id = p.policy_id WHERE p.policy_id = %s",
            (policy_id,),
        )
        if not policy:
            raise IdentitySecurityError("policy not found")
        if not policy["document_available"]:
            return {**policy, "risk": "incomplete", "message": "Policy permission details unavailable. Risk assessment is incomplete."}
        document = _json(policy["policy_document"])
        actions, resources = _actions_resources(document)
        affected = self._query(
            "SELECT source_id, relationship_type, evidence FROM relationships "
            "WHERE target_id = %s ORDER BY source_id",
            (policy_id,),
        )
        paths = self._query(
            "SELECT path_id, principal_id, target_id, risk, evidence FROM privilege_paths "
            "WHERE evidence->>'policy' = %s ORDER BY risk DESC",
            (policy_id,),
        )
        return {**policy, "actions": actions, "resources": resources, "affected_identities": affected, "affected_privilege_paths": paths, "risk": _risk(actions, resources)}

    def simulate_remediation(self, change: Mapping[str, Any]) -> dict[str, Any]:
        """Store a proposed change and return evidence-backed before/after impact."""
        with self._connection(write=True) as connection:
            with connection.cursor() as cursor:
                before = self._read_state(cursor)
                after = self._apply_change(before, change)
                simulation = self._simulation(before, after)
                plan_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO remediation_plans (plan_id, status, change, before_document, after_document, simulation) "
                    "VALUES (%s, 'proposed', %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)",
                    (plan_id, _dump(dict(change)), _dump(before), _dump(after), _dump(simulation)),
                )
        return {"plan_id": plan_id, "status": "proposed", **simulation}

    def apply_remediation(self, plan_id: str, approval: str) -> dict[str, Any]:
        """Apply one simulated plan only after exact approval, then verify and audit it."""
        if approval != APPROVAL_PHRASE:
            raise IdentitySecurityError("approval must be exactly: Approve this change")
        with self._connection(write=True) as connection:
            with connection.cursor() as cursor:
                plan = self._one_cursor(cursor, "SELECT * FROM remediation_plans WHERE plan_id = %s FOR UPDATE", (plan_id,))
                if not plan:
                    raise IdentitySecurityError("remediation plan not found")
                if plan["status"] != "proposed":
                    raise IdentitySecurityError("remediation plan is not proposed")
                after = _json(plan["after_document"])
                cursor.execute("UPDATE remediation_plans SET status = 'approved' WHERE plan_id = %s", (plan_id,))
                self._write_state(cursor, after)
                self._rebuild(cursor, after)
                audit_id = self._write_audit(cursor, plan_id, "apply_remediation", "verifying", {"approval": APPROVAL_PHRASE})
                verification = self._verify_cursor(cursor, plan_id, after, audit_id)
                cursor.execute(
                    "UPDATE remediation_plans SET status = 'completed', completed_at = now() WHERE plan_id = %s",
                    (plan_id,),
                )
                cursor.execute(
                    "UPDATE audit_logs SET status = 'completed', details = %s::jsonb WHERE audit_id = %s",
                    (_dump({"approval": APPROVAL_PHRASE, "verification": verification}), audit_id),
                )
        return {"plan_id": plan_id, "change_completed": True, "verification": verification, "audit_id": audit_id}

    def verify_remediation(self, plan_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                plan = self._one_cursor(cursor, "SELECT after_document, simulation, status FROM remediation_plans WHERE plan_id = %s", (plan_id,))
                if not plan:
                    raise IdentitySecurityError("remediation plan not found")
                return self._verify_cursor(cursor, plan_id, _json(plan["after_document"]))

    def mark_finding_resolved(self, finding_id: str, plan_id: str) -> None:
        verification = self.verify_remediation(plan_id)
        if not verification["verified"]:
            raise IdentitySecurityError("finding cannot be resolved before successful verification")
        with self._connection(write=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE security_findings SET status = 'resolved' WHERE finding_id = %s", (finding_id,))
                if cursor.rowcount != 1:
                    raise IdentitySecurityError("security finding not found")
                self._write_audit(cursor, plan_id, "mark_finding_resolved", "completed", {"finding_id": finding_id})

    def _write_state(self, cursor: Any, document: Mapping[str, Any]) -> None:
        cursor.execute(
            "INSERT INTO identity_state (id, document, updated_at) VALUES (1, %s::jsonb, now()) "
            "ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document, updated_at = now()",
            (_dump(document),),
        )

    def _read_state(self, cursor: Any) -> dict[str, Any]:
        state = self._one_cursor(cursor, "SELECT document FROM identity_state WHERE id = 1")
        if not state:
            raise IdentitySecurityError("no local identity inventory has been imported")
        return _json(state["document"])

    def _rebuild(self, cursor: Any, document: Mapping[str, Any]) -> dict[str, int]:
        cursor.execute("DELETE FROM security_findings")
        cursor.execute("DELETE FROM privilege_paths")
        cursor.execute("DELETE FROM relationships")
        cursor.execute("DELETE FROM policies")
        cursor.execute("DELETE FROM identity_entities")
        entities, policies, relationships = _normalize(document)
        for entity in entities.values():
            cursor.execute(
                "INSERT INTO identity_entities (entity_id, entity_type, name, data) VALUES (%s, %s, %s, %s::jsonb)",
                (entity["entity_id"], entity["entity_type"], entity["name"], _dump(entity["data"])),
            )
        for policy in policies.values():
            cursor.execute(
                "INSERT INTO policies (policy_id, policy_document, document_available) VALUES (%s, %s::jsonb, %s)",
                (policy["policy_id"], _dump(policy["policy_document"]), policy["document_available"]),
            )
        for relationship in relationships.values():
            cursor.execute(
                "INSERT INTO relationships (relationship_id, source_id, target_id, relationship_type, evidence) "
                "VALUES (%s, %s, %s, %s, %s::jsonb)",
                (relationship["relationship_id"], relationship["source_id"], relationship["target_id"], relationship["relationship_type"], _dump(relationship["evidence"])),
            )
        report = analyze_inventory(document)
        for finding in report["findings"]:
            path_id = _stable_id("path", finding)
            evidence = {"finding": finding, "policy": _policy_from_path(finding.get("path", []))}
            cursor.execute(
                "INSERT INTO privilege_paths (path_id, principal_id, target_id, risk, evidence) VALUES (%s, %s, %s, %s, %s::jsonb)",
                (path_id, finding["principal"], finding["resource"], finding["severity"], _dump(evidence)),
            )
            cursor.execute(
                "INSERT INTO security_findings (finding_id, path_id, title, risk, evidence) VALUES (%s, %s, %s, %s, %s::jsonb)",
                (_stable_id("finding", finding), path_id, finding["reason"], finding["severity"], _dump(evidence)),
            )
        return {"entities": len(entities), "policies": len(policies), "relationships": len(relationships), "findings": len(report["findings"])}

    def _apply_change(self, before: Mapping[str, Any], change: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(change.get("operation", ""))
        if operation not in _OPERATIONS:
            raise IdentitySecurityError("unsupported remediation operation")
        document = _copy_document(before)
        if operation in {"remove_user_policy", "detach_policy"}:
            entity_type = "user" if operation == "remove_user_policy" else str(change.get("entity_type", ""))
            name = str(change.get("user_name") if operation == "remove_user_policy" else change.get("entity_name", ""))
            policy_name = _required(change, "policy_name")
            section, name_key, attached, inline = _entity_section(entity_type)
            item = _named(document.get(section, []), name_key, name)
            _remove_policy(item, policy_name, attached, inline)
        elif operation == "remove_group_membership":
            user_name, group_name = _required(change, "user_name"), _required(change, "group_name")
            user = _named(document.get("UserDetailList", []), "UserName", user_name)
            group = _named(document.get("GroupDetailList", []), "GroupName", group_name)
            user["GroupList"] = [value for value in _list(user.get("GroupList")) if value != group_name]
            group["Users"] = [value for value in _list(group.get("Users")) if _member_name(value) != user_name]
        elif operation in {"remove_role_relationship", "update_trust_relationship"}:
            role = _named(document.get("RoleDetailList", []), "RoleName", _required(change, "role_name"))
            _remove_trust_principal(role, _required(change, "principal"))
        else:
            policy = _find_policy(document, _required(change, "policy_name"))
            statements = _statements(policy.get("PolicyDocument", {}))
            index = change.get("statement_index")
            if not isinstance(index, int) or index < 0 or index >= len(statements):
                raise IdentitySecurityError("statement_index must select an existing policy statement")
            for source, key in (("actions", "Action"), ("resources", "Resource")):
                if source in change:
                    value = change[source]
                    if not isinstance(value, (str, list)):
                        raise IdentitySecurityError(f"{source} must be a string or list")
                    statements[index][key] = value
        return document

    def _simulation(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
        before_findings = analyze_inventory(before)["findings"]
        after_findings = analyze_inventory(after)["findings"]
        before_paths = {_stable_id("path", finding) for finding in before_findings}
        after_paths = {_stable_id("path", finding) for finding in after_findings}
        return {
            "paths_before": len(before_paths),
            "paths_after": len(after_paths),
            "paths_broken": len(before_paths - after_paths),
            "paths_remaining": len(after_paths),
            "risk_before": _risk_summary(before_findings),
            "risk_after": _risk_summary(after_findings),
        }

    def _verify_cursor(self, cursor: Any, plan_id: str, expected_after: Mapping[str, Any], audit_id: str | None = None) -> dict[str, Any]:
        state = self._read_state(cursor)
        if audit_id:
            audit = self._one_cursor(cursor, "SELECT audit_id FROM audit_logs WHERE audit_id = %s", (audit_id,))
        else:
            audit = self._one_cursor(cursor, "SELECT audit_id FROM audit_logs WHERE plan_id = %s", (plan_id,))
        paths = self._one_cursor(cursor, "SELECT COUNT(*) AS count FROM privilege_paths") or {"count": 0}
        return {
            "verified": state == dict(expected_after) and bool(audit),
            "database_record_changed": state == dict(expected_after),
            "audit_record_exists": bool(audit),
            "paths_after": int(paths["count"]),
        }

    def _write_audit(self, cursor: Any, plan_id: str | None, action: str, status: str, details: Mapping[str, Any]) -> str:
        audit_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO audit_logs (audit_id, plan_id, action, status, details) VALUES (%s, %s, %s, %s, %s::jsonb)",
            (audit_id, plan_id, action, status, _dump(details)),
        )
        return audit_id

    def _query(self, statement: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                return _rows(cursor)

    def _one(self, statement: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                return self._one_cursor(cursor, statement, params)

    def _one_cursor(self, cursor: Any, statement: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        cursor.execute(statement, params)
        row = cursor.fetchone()
        return _row(cursor, row) if row is not None else None

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[Any]:
        connection = self._connect()
        try:
            yield connection
            if write:
                connection.commit()
        except Exception:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self) -> Any:
        if self._connection_factory:
            return self._connection_factory()
        if not self._database_url:
            raise IdentitySecurityError("CY06_DATABASE_URL is required for local PostgreSQL")
        try:
            import psycopg
        except ImportError as error:
            raise IdentitySecurityError("PostgreSQL driver unavailable; install project dependencies") from error
        try:
            return psycopg.connect(self._database_url)
        except Exception as error:
            raise IdentitySecurityError("cannot connect to local PostgreSQL") from error


def _normalize(document: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    entities: dict[str, dict[str, Any]] = {}
    policies: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}

    def entity(kind: str, name: str, data: Mapping[str, Any], identifier: str | None = None) -> str:
        entity_id = identifier or str(data.get("Arn") or data.get("PolicyArn") or data.get("ResourceArn") or f"{kind}:{name}")
        entities.setdefault(entity_id, {"entity_id": entity_id, "entity_type": kind, "name": name, "data": dict(data)})
        return entity_id

    def relationship(source: str, target: str, kind: str, evidence: Mapping[str, Any]) -> None:
        relationship_id = _stable_id("relationship", {"source": source, "target": target, "kind": kind})
        relationships[relationship_id] = {"relationship_id": relationship_id, "source_id": source, "target_id": target, "relationship_type": kind, "evidence": dict(evidence)}

    def policy(item: Mapping[str, Any], owner: str | None = None) -> str:
        name = str(item.get("PolicyName") or item.get("PolicyId") or "unnamed-policy")
        policy_id = entity("policy", name, item, str(item.get("Arn") or item.get("PolicyArn") or f"policy:{owner or 'managed'}:{name}"))
        document_value = item.get("PolicyDocument")
        policies[policy_id] = {"policy_id": policy_id, "policy_document": document_value if isinstance(document_value, dict) else {}, "document_available": isinstance(document_value, dict)}
        for action, resource in _statement_resources(document_value):
            resource_id = entity("resource", resource, {"ResourceArn": resource}, resource)
            relationship(policy_id, resource_id, "grants", {"action": action, "resource": resource})
        return policy_id

    groups = {str(item.get("GroupName")): item for item in _list(document.get("GroupDetailList")) if isinstance(item, dict)}
    for item in groups.values():
        entity("group", str(item.get("GroupName")), item)
    roles = {str(item.get("RoleName")): item for item in _list(document.get("RoleDetailList")) if isinstance(item, dict)}
    for item in roles.values():
        entity("role", str(item.get("RoleName")), item)
    for item in _list(document.get("Policies")):
        if isinstance(item, dict):
            policy(item)
    policy_by_name = {value["name"]: key for key, value in entities.items() if value["entity_type"] == "policy"}
    users = {str(item.get("UserName")): item for item in _list(document.get("UserDetailList")) if isinstance(item, dict)}

    for user in users.values():
        user_id = entity("user", str(user.get("UserName")), user)
        for group_name in _list(user.get("GroupList")):
            group = groups.get(str(group_name))
            group_id = entity("group", str(group_name), group or {"GroupName": str(group_name)})
            relationship(user_id, group_id, "member_of", {"group": str(group_name)})
        _attach_policies(user, user_id, policy, policy_by_name, relationship)
    for group in groups.values():
        group_id = entity("group", str(group.get("GroupName")), group)
        for member in _list(group.get("Users")):
            name = _member_name(member)
            if name:
                user_id = entity("user", name, users.get(name) or {"UserName": name})
                relationship(user_id, group_id, "member_of", {"group": group["GroupName"]})
        _attach_policies(group, group_id, policy, policy_by_name, relationship)
    for role in roles.values():
        role_id = entity("role", str(role.get("RoleName")), role)
        _attach_policies(role, role_id, policy, policy_by_name, relationship)
        for statement in _statements(role.get("AssumeRolePolicyDocument", {})):
            principal = statement.get("Principal") if isinstance(statement, dict) else None
            for source in _principals(principal):
                source_id = entity("principal", source, {"identifier": source}, source)
                relationship(source_id, role_id, "trusts", {"statement": statement})
    return entities, policies, relationships


def _attach_policies(item: Mapping[str, Any], owner_id: str, add_policy: Callable[[Mapping[str, Any], str | None], str], by_name: Mapping[str, str], add_relationship: Callable[[str, str, str, Mapping[str, Any]], None]) -> None:
    for policy_item in _list(item.get("AttachedManagedPolicies")):
        if not isinstance(policy_item, dict):
            continue
        name = str(policy_item.get("PolicyName") or "unnamed-policy")
        policy_id = by_name.get(name) or add_policy(policy_item, owner_id)
        add_relationship(owner_id, policy_id, "attached_policy", {"source": "managed"})
    for policy_item in _list(item.get("UserPolicyList") or item.get("GroupPolicyList") or item.get("RolePolicyList")):
        if isinstance(policy_item, dict):
            add_relationship(owner_id, add_policy(policy_item, owner_id), "attached_policy", {"source": "inline"})


def _copy_document(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise IdentitySecurityError("identity inventory must be an object")
    return copy.deepcopy(dict(value))


def _required(change: Mapping[str, Any], key: str) -> str:
    value = change.get(key)
    if not isinstance(value, str) or not value:
        raise IdentitySecurityError(f"{key} is required")
    return value


def _entity_section(entity_type: str) -> tuple[str, str, str, str]:
    sections = {
        "user": ("UserDetailList", "UserName", "AttachedManagedPolicies", "UserPolicyList"),
        "group": ("GroupDetailList", "GroupName", "AttachedManagedPolicies", "GroupPolicyList"),
        "role": ("RoleDetailList", "RoleName", "AttachedManagedPolicies", "RolePolicyList"),
    }
    try:
        return sections[entity_type]
    except KeyError as error:
        raise IdentitySecurityError("entity_type must be user, group, or role") from error


def _named(items: Any, key: str, name: str) -> dict[str, Any]:
    for item in _list(items):
        if isinstance(item, dict) and item.get(key) == name:
            return item
    raise IdentitySecurityError("target record not found")


def _remove_policy(item: dict[str, Any], policy_name: str, attached_key: str, inline_key: str) -> None:
    before = len(_list(item.get(attached_key))) + len(_list(item.get(inline_key)))
    item[attached_key] = [value for value in _list(item.get(attached_key)) if not isinstance(value, dict) or value.get("PolicyName") != policy_name]
    item[inline_key] = [value for value in _list(item.get(inline_key)) if not isinstance(value, dict) or value.get("PolicyName") != policy_name]
    if before == len(item[attached_key]) + len(item[inline_key]):
        raise IdentitySecurityError("policy attachment not found")


def _remove_trust_principal(role: dict[str, Any], principal: str) -> None:
    statements = _statements(role.get("AssumeRolePolicyDocument", {}))
    changed = False
    kept = []
    for statement in statements:
        principals = _principals(statement.get("Principal") if isinstance(statement, dict) else None)
        if principal not in principals:
            kept.append(statement)
            continue
        changed = True
        remaining = [value for value in principals if value != principal]
        if remaining:
            statement = copy.deepcopy(statement)
            statement["Principal"] = {"AWS": remaining if len(remaining) > 1 else remaining[0]}
            kept.append(statement)
    if not changed:
        raise IdentitySecurityError("trust relationship not found")
    role.setdefault("AssumeRolePolicyDocument", {})["Statement"] = kept


def _find_policy(document: Mapping[str, Any], name: str) -> dict[str, Any]:
    for item in _list(document.get("Policies")):
        if isinstance(item, dict) and item.get("PolicyName") == name:
            return item
    for section, key in (("UserDetailList", "UserPolicyList"), ("GroupDetailList", "GroupPolicyList"), ("RoleDetailList", "RolePolicyList")):
        for entity in _list(document.get(section)):
            if isinstance(entity, dict):
                for item in _list(entity.get(key)):
                    if isinstance(item, dict) and item.get("PolicyName") == name:
                        return item
    raise IdentitySecurityError("policy not found")


def _statements(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        return []
    statements = document.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
        document["Statement"] = statements
    return [statement for statement in statements if isinstance(statement, dict)] if isinstance(statements, list) else []


def _statement_resources(document: Any) -> Iterator[tuple[str, str]]:
    for statement in _statements(document):
        for action in _strings(statement.get("Action")):
            for resource in _strings(statement.get("Resource")):
                yield action, resource


def _actions_resources(document: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    pairs = list(_statement_resources(document))
    return sorted({action for action, _ in pairs}), sorted({resource for _, resource in pairs})


def _principals(value: Any) -> list[str]:
    if isinstance(value, dict):
        return _strings(value.get("AWS"))
    return _strings(value)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _member_name(value: Any) -> str:
    return str(value.get("UserName", "")) if isinstance(value, dict) else str(value) if isinstance(value, str) else ""


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{uuid.uuid5(uuid.NAMESPACE_URL, _dump(value))}"


def _policy_from_path(path: Any) -> str | None:
    return next((str(value) for value in _list(path) if isinstance(value, str) and "policy" in value.lower()), None)


def _risk(actions: list[str], resources: list[str]) -> str:
    return "critical" if "*" in actions and "*" in resources else "high" if "*" in actions or "*" in resources else "medium"


def _risk_summary(findings: list[Mapping[str, Any]]) -> dict[str, int]:
    return {level: sum(item.get("severity") == level for item in findings) for level in ("critical", "high", "medium", "low")}


def _limit(value: int) -> int:
    return max(1, min(int(value), 200))


def _offset(value: int) -> int:
    return max(0, int(value))


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise IdentitySecurityError("stored local identity data is invalid")


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    names = [column.name if hasattr(column, "name") else column[0] for column in cursor.description]
    return dict(zip(names, value, strict=True))


def _rows(cursor: Any) -> list[dict[str, Any]]:
    return [_row(cursor, value) for value in cursor.fetchall()]
