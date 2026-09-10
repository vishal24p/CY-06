import pytest

from cy06.identity_security import APPROVAL_PHRASE, IdentitySecurityError, IdentitySecurityTools, _normalize


def inventory():
    user_arn = "arn:aws:iam::000000000000:user/analyst"
    role_arn = "arn:aws:iam::000000000000:role/DeploymentRole"
    return {
        "UserDetailList": [{
            "UserName": "analyst", "Arn": user_arn, "GroupList": ["operators"],
            "AttachedManagedPolicies": [],
            "UserPolicyList": [{"PolicyName": "AssumeDeploymentRole", "PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn}]}}],
        }],
        "GroupDetailList": [{"GroupName": "operators", "Arn": "arn:aws:iam::000000000000:group/operators", "Users": [{"UserName": "analyst"}], "AttachedManagedPolicies": [], "GroupPolicyList": []}],
        "RoleDetailList": [{"RoleName": "DeploymentRole", "Arn": role_arn, "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"AWS": user_arn}, "Action": "sts:AssumeRole"}]}, "AttachedManagedPolicies": [{"PolicyName": "AdministratorAccess"}], "RolePolicyList": []}],
        "Policies": [],
    }


class Cursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, params=None):
        self.executed.append((statement, params))


class Connection:
    def __init__(self):
        self.cursor_instance = Cursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class ApplyCursor(Cursor):
    def __init__(self, plan, after):
        super().__init__()
        self.plan = plan
        self.after = after
        self.result = None
        self.rowcount = 1

    def execute(self, statement, params=None):
        super().execute(statement, params)
        if statement.startswith("SELECT * FROM remediation_plans"):
            self.result = self.plan
        elif statement.startswith("SELECT document FROM identity_state"):
            self.result = {"document": self.after}
        elif statement.startswith("SELECT audit_id FROM audit_logs"):
            self.result = {"audit_id": "audit-id"}
        elif statement.startswith("SELECT COUNT(*)"):
            self.result = {"count": 0}
        else:
            self.result = None

    def fetchone(self):
        return self.result


class ApplyConnection(Connection):
    def __init__(self, plan, after):
        super().__init__()
        self.cursor_instance = ApplyCursor(plan, after)


def test_initialize_uses_static_schema_and_commits():
    connection = Connection()
    IdentitySecurityTools(connection_factory=lambda: connection).initialize()

    statement, params = connection.cursor_instance.executed[0]
    assert "CREATE TABLE IF NOT EXISTS identity_entities" in statement
    assert params is None
    assert connection.committed and connection.closed


def test_database_url_is_required_without_injected_connection(monkeypatch):
    monkeypatch.delenv("CY06_DATABASE_URL", raising=False)

    with pytest.raises(IdentitySecurityError, match="CY06_DATABASE_URL"):
        IdentitySecurityTools().initialize()


def test_group_membership_simulation_removes_privilege_path():
    tools = IdentitySecurityTools(connection_factory=lambda: Connection())
    before = inventory()
    after = tools._apply_change(before, {"operation": "remove_user_policy", "user_name": "analyst", "policy_name": "AssumeDeploymentRole"})

    simulation = tools._simulation(before, after)

    assert simulation["paths_before"] == 1
    assert simulation["paths_after"] == 0
    assert simulation["paths_broken"] == 1


def test_apply_requires_exact_approval_phrase_before_database_access():
    tools = IdentitySecurityTools(connection_factory=lambda: (_ for _ in ()).throw(AssertionError("database should not be opened")))

    with pytest.raises(IdentitySecurityError, match="exactly"):
        tools.apply_remediation("plan-id", "approved")

    assert APPROVAL_PHRASE == "Approve this change"


def test_entity_sort_field_is_allowlisted_before_database_access():
    tools = IdentitySecurityTools(connection_factory=lambda: (_ for _ in ()).throw(AssertionError("database should not be opened")))

    with pytest.raises(IdentitySecurityError, match="sort_by"):
        tools.list_identity_entities(sort_by="name; DROP TABLE identity_entities")


def test_group_membership_reuses_imported_user_identifier():
    entities, _, relationships = _normalize(inventory())
    user_arn = "arn:aws:iam::000000000000:user/analyst"

    membership = next(value for value in relationships.values() if value["relationship_type"] == "member_of")
    assert membership["source_id"] == user_arn
    assert [value for value in entities.values() if value["entity_type"] == "user"] == [entities[user_arn]]


def test_missing_policy_document_reports_incomplete_impact(monkeypatch):
    tools = IdentitySecurityTools(connection_factory=lambda: Connection())
    monkeypatch.setattr(tools, "_one", lambda *_: {"policy_id": "policy-id", "name": "Unknown", "policy_document": {}, "document_available": False})

    result = tools.analyze_policy_impact("policy-id")

    assert result["risk"] == "incomplete"
    assert "unavailable" in result["message"]


def test_apply_rebuilds_then_verifies_and_audits():
    tools = IdentitySecurityTools(connection_factory=lambda: Connection())
    before = inventory()
    after = tools._apply_change(before, {"operation": "remove_user_policy", "user_name": "analyst", "policy_name": "AssumeDeploymentRole"})
    plan = {"plan_id": "plan-id", "status": "proposed", "after_document": after}
    connection = ApplyConnection(plan, after)
    tools = IdentitySecurityTools(connection_factory=lambda: connection)

    result = tools.apply_remediation("plan-id", APPROVAL_PHRASE)

    statements = [statement for statement, _ in connection.cursor_instance.executed]
    assert result["verification"]["verified"]
    assert statements.index("DELETE FROM security_findings") < next(i for i, statement in enumerate(statements) if "INSERT INTO audit_logs" in statement)
    assert connection.committed and connection.closed
