from cy06.rules.engine import analyze_inventory


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

    assert analyze_inventory(inventory)["findings"] == []
