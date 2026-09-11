import json
from pathlib import Path

from cy06.rules.engine import analyze_inventory


def test_findings_are_returned_in_risk_order():
    inventory = {
        "UserDetailList": [{
            "UserName": "analyst",
            "Arn": "arn:aws:iam::000000000000:user/analyst",
            "GroupList": [],
            "AttachedManagedPolicies": [],
            "UserPolicyList": [{
                "PolicyName": "MixedRisk",
                "PolicyDocument": {"Statement": [{
                    "Effect": "Allow",
                    "Action": ["iam:AttachRolePolicy", "iam:CreateUser"],
                    "Resource": "*",
                }]},
            }],
        }],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }

    assert [item["severity"] for item in analyze_inventory(inventory)["findings"]] == ["critical", "high"]


def test_group_inherited_iam_mutation_is_reported():
    inventory = {
        "UserDetailList": [
            {
                "UserName": "employee2",
                "Arn": "arn:aws:iam::000000000000:user/employee2",
                "GroupList": ["Developers"],
                "UserPolicyList": [],
                "AttachedManagedPolicies": [],
            }
        ],
        "GroupDetailList": [
            {
                "GroupName": "Developers",
                "Users": ["employee2"],
                "AttachedManagedPolicies": [],
                "GroupPolicyList": [
                    {
                        "PolicyName": "UserManagementPolicy",
                        "PolicyDocument": {
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["iam:CreateUser", "iam:DeleteUser"],
                                    "Resource": "*",
                                }
                            ]
                        },
                    }
                ],
            }
        ],
        "RoleDetailList": [],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    assert {finding["permission"] for finding in report["findings"]} == {
        "iam:CreateUser",
        "iam:DeleteUser",
    }
    assert all(finding["rule_id"] == "IAM-003" for finding in report["findings"])
    assert all("Developers" in finding["path"] for finding in report["findings"])


def test_user_can_assume_privileged_role_is_reported():
    user_arn = "arn:aws:iam::000000000000:user/analyst"
    role_arn = "arn:aws:iam::000000000000:role/DeploymentRole"
    inventory = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "Arn": user_arn,
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "UserPolicyList": [
                    {
                        "PolicyName": "AssumeDeploymentRole",
                        "PolicyDocument": {
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "sts:AssumeRole",
                                    "Resource": role_arn,
                                }
                            ]
                        },
                    }
                ],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [
            {
                "RoleName": "DeploymentRole",
                "Arn": role_arn,
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": user_arn},
                            "Action": "sts:AssumeRole",
                        }
                    ]
                },
                "AttachedManagedPolicies": [{"PolicyName": "AdministratorAccess"}],
                "RolePolicyList": [],
                "InstanceProfileList": [],
            }
        ],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    finding = next(item for item in report["findings"] if item["rule_id"] == "IAM-005")
    assert finding["principal"] == user_arn
    assert "DeploymentRole" in finding["path"]


def test_group_permission_can_reach_admin_through_two_roles():
    user_arn = "arn:aws:iam::000000000000:user/analyst"
    deployment_arn = "arn:aws:iam::000000000000:role/DeploymentRole"
    admin_arn = "arn:aws:iam::000000000000:role/AdminRole"
    inventory = {
        "UserDetailList": [{
            "UserName": "analyst",
            "Arn": user_arn,
            "GroupList": ["Developers"],
            "AttachedManagedPolicies": [],
            "UserPolicyList": [],
        }],
        "GroupDetailList": [{
            "GroupName": "Developers",
            "Users": ["analyst"],
            "AttachedManagedPolicies": [],
            "GroupPolicyList": [{
                "PolicyName": "AssumeDeployment",
                "PolicyDocument": {"Statement": [{
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Resource": deployment_arn,
                }]},
            }],
        }],
        "RoleDetailList": [
            {
                "RoleName": "DeploymentRole",
                "Arn": deployment_arn,
                "AssumeRolePolicyDocument": {"Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": user_arn},
                    "Action": "sts:AssumeRole",
                }]},
                "AttachedManagedPolicies": [],
                "RolePolicyList": [{
                    "PolicyName": "AssumeAdmin",
                    "PolicyDocument": {"Statement": [{
                        "Effect": "Allow",
                        "Action": "sts:AssumeRole",
                        "Resource": admin_arn,
                    }]},
                }],
            },
            {
                "RoleName": "AdminRole",
                "Arn": admin_arn,
                "AssumeRolePolicyDocument": {"Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": deployment_arn},
                    "Action": "sts:AssumeRole",
                }]},
                "AttachedManagedPolicies": [{"PolicyName": "AdministratorAccess"}],
                "RolePolicyList": [],
            },
        ],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    assert report["paths"][0]["principal"] == user_arn
    assert report["paths"][0]["target"] == admin_arn
    assert report["paths"][0]["hops"] == 2
    assert report["paths"][0]["path"] == [
        user_arn,
        "group:Developers",
        "policy:AssumeDeployment",
        "sts:AssumeRole",
        "DeploymentRole",
        "policy:AssumeAdmin",
        "sts:AssumeRole",
        "AdminRole",
    ]


def test_guided_path_reports_truthful_explainable_risk_and_exact_remediation():
    inventory = json.loads(
        (Path(__file__).parents[1] / "data" / "simple-demo-iam-inventory.json").read_text(
            encoding="utf-8"
        )
    )

    report = analyze_inventory(inventory)

    path = report["paths"][0]
    assert report["summary"]["paths"] == 1
    assert report["summary"]["critical"] == 1
    assert path["starting_privilege"] == "low"
    assert set(path["score_breakdown"]) == {
        "target_impact",
        "assumption_resource_breadth",
        "hop_directness",
        "source_context",
        "confidence",
    }
    assert sum(path["score_breakdown"].values()) == path["risk_score"]
    assert 0 <= path["risk_score"] <= 100
    assert path["remediation"] == {
        "policy_name": "CanEnterAdmin",
        "statement_index": 0,
        "action": "sts:AssumeRole",
        "resource": "arn:aws:iam::000000000000:role/AdminRole",
    }


def test_remediation_locator_preserves_raw_statement_index():
    inventory = json.loads(
        (Path(__file__).parents[1] / "data" / "simple-demo-iam-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    statements = inventory["RoleDetailList"][0]["RolePolicyList"][0]["PolicyDocument"]["Statement"]
    statements.insert(0, None)
    statements.append({"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "other-role"})

    locator = analyze_inventory(inventory)["paths"][0]["remediation"]

    assert locator["statement_index"] == 1
    selected = statements[locator["statement_index"]]
    assert selected["Resource"] == locator["resource"]
    selected["Action"] = []
    assert analyze_inventory(inventory)["paths"] == []
    assert statements[2]["Action"] == "sts:AssumeRole"


def test_conditional_trust_marks_the_whole_path_for_review():
    inventory = json.loads(
        (Path(__file__).parents[1] / "data" / "simple-demo-iam-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    inventory["RoleDetailList"][0]["AssumeRolePolicyDocument"]["Statement"][0][
        "Condition"
    ] = {"StringEquals": {"sts:ExternalId": "required-id"}}

    report = analyze_inventory(inventory)

    assert report["paths"][0]["confidence"] == "review_required"
    assert report["paths"][0]["score_breakdown"]["confidence"] == 0
    assert {
        "code": "review_required",
        "feature": "TrustPolicyCondition",
        "role": "DeploymentRole",
    } in report["warnings"]


def test_explicit_deny_suppresses_matching_allow():
    inventory = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "Arn": "arn:aws:iam::000000000000:user/analyst",
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "UserPolicyList": [
                    {
                        "PolicyName": "AllowDelete",
                        "PolicyDocument": {
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "iam:DeleteUser",
                                    "Resource": "*",
                                }
                            ]
                        },
                    },
                    {
                        "PolicyName": "DenyDelete",
                        "PolicyDocument": {
                            "Statement": [
                                {
                                    "Effect": "Deny",
                                    "Action": "iam:DeleteUser",
                                    "Resource": "*",
                                }
                            ]
                        },
                    },
                ],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    assert report["findings"] == []


def test_condition_is_reported_for_review():
    inventory = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "Arn": "arn:aws:iam::000000000000:user/analyst",
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "UserPolicyList": [
                    {
                        "PolicyName": "ConditionalDelete",
                        "PolicyDocument": {
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "iam:DeleteUser",
                                    "Resource": "*",
                                    "Condition": {"Bool": {"aws:MultiFactorAuthPresent": "true"}},
                                }
                            ]
                        },
                    }
                ],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    assert report["findings"][0]["confidence"] == "review_required"
    assert any(item["feature"] == "Condition" for item in report["warnings"])


def test_scoped_action_wildcard_is_not_unrestricted_access():
    inventory = {
        "UserDetailList": [
            {
                "UserName": "auditor",
                "Arn": "arn:aws:iam::000000000000:user/auditor",
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "UserPolicyList": [
                    {
                        "PolicyName": "ReadOnly",
                        "PolicyDocument": {
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "iam:Get*",
                                    "Resource": "*",
                                }
                            ]
                        },
                    }
                ],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    assert report["findings"] == []
    assert report["paths"] == []


def test_permissions_boundary_deny_suppresses_identity_finding():
    inventory = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "Arn": "arn:aws:iam::000000000000:user/analyst",
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "PermissionsBoundary": {
                    "PolicyDocument": {
                        "Statement": [{"Effect": "Deny", "Action": "iam:DeleteUser", "Resource": "*"}]
                    }
                },
                "UserPolicyList": [
                    {
                        "PolicyName": "DeleteUsers",
                        "PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "iam:DeleteUser", "Resource": "*"}]},
                    }
                ],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }

    assert analyze_inventory(inventory)["findings"] == []


def test_scp_deny_suppresses_role_assumption_path():
    user_arn = "arn:aws:iam::000000000000:user/analyst"
    role_arn = "arn:aws:iam::000000000000:role/DeploymentRole"
    inventory = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "Arn": user_arn,
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "UserPolicyList": [{"PolicyName": "Assume", "PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn}]}}],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [{
            "RoleName": "DeploymentRole",
            "Arn": role_arn,
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"AWS": user_arn}, "Action": "sts:AssumeRole"}]},
            "AttachedManagedPolicies": [{"PolicyName": "AdministratorAccess"}],
            "RolePolicyList": [],
        }],
        "Policies": [],
        "Organizations": {
            "Accounts": [{"Id": "000000000000", "ParentId": "r-root"}],
            "SCPs": [{"PolicyName": "DenyRoleAssumption", "TargetIds": ["000000000000"], "PolicyDocument": {"Statement": [{"Effect": "Deny", "Action": "sts:AssumeRole", "Resource": "*"}]}}],
        },
    }

    report = analyze_inventory(inventory)

    assert report["findings"] == []
    assert report["paths"] == []


def test_resource_policy_deny_suppresses_unrestricted_identity_finding():
    inventory = {
        "UserDetailList": [{
            "UserName": "analyst",
            "Arn": "arn:aws:iam::000000000000:user/analyst",
            "GroupList": [],
            "AttachedManagedPolicies": [],
            "UserPolicyList": [{"PolicyName": "Wide", "PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}}],
        }],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
        "ResourcePolicies": [{"ResourceArn": "*", "PolicyName": "DenyAll", "PolicyDocument": {"Statement": [{"Effect": "Deny", "Principal": {"AWS": "arn:aws:iam::000000000000:user/analyst"}, "Action": "*", "Resource": "*"}]}}],
    }

    assert analyze_inventory(inventory)["findings"] == []


def test_real_aws_group_list_applies_group_permissions():
    user_arn = "arn:aws:iam::000000000000:user/analyst"
    role_arn = "arn:aws:iam::000000000000:role/Admin"
    inventory = {
        "UserDetailList": [{"UserName": "analyst", "Arn": user_arn, "GroupList": ["Developers"], "AttachedManagedPolicies": [], "UserPolicyList": []}],
        "GroupDetailList": [{"GroupName": "Developers", "AttachedManagedPolicies": [], "GroupPolicyList": [{"PolicyName": "AssumeAdmin", "PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn}]}}]}],
        "RoleDetailList": [{"RoleName": "Admin", "Arn": role_arn, "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"AWS": user_arn}, "Action": "sts:AssumeRole"}]}, "AttachedManagedPolicies": [{"PolicyName": "AdministratorAccess"}], "RolePolicyList": []}],
        "Policies": [],
    }

    report = analyze_inventory(inventory)

    assert report["paths"][0]["target"] == role_arn
