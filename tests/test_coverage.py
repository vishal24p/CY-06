from cy06.coverage import build_coverage


def test_coverage_graph_joins_identity_metadata_and_boundary():
    user_arn = "arn:aws:iam::000000000000:user/analyst"
    inventory = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "Arn": user_arn,
                "PermissionsBoundary": {
                    "PermissionsBoundaryArn": "arn:aws:iam::000000000000:policy/AnalystBoundary",
                    "PolicyName": "AnalystBoundary",
                },
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
        "IdentityMetadata": [
            {
                "PrincipalArn": user_arn,
                "EmployeeId": "EMP-1001",
                "DisplayName": "Aarav Sharma",
                "JobTitle": "Data Analyst",
                "Department": "Analytics",
            }
        ],
    }

    result = build_coverage(inventory)

    assert result["metadata"][0]["job_title"] == "Data Analyst"
    assert {edge["type"] for edge in result["edges"]} >= {"described_by", "bounded_by"}
    assert result["coverage"]["identity_metadata"] == 1


def test_coverage_graph_models_resource_policy_and_scp_hierarchy():
    inventory = {
        "UserDetailList": [],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
        "ResourcePolicies": [
            {
                "ResourceArn": "arn:aws:s3:::company-data",
                "ResourceType": "s3_bucket",
                "PolicyName": "CompanyDataPolicy",
                "PolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "arn:aws:iam::000000000000:role/DataRole"},
                            "Action": "s3:GetObject",
                            "Resource": "arn:aws:s3:::company-data/*",
                        }
                    ]
                },
            }
        ],
        "Organizations": {
            "OrganizationId": "o-example",
            "RootId": "r-root",
            "OUs": [{"Id": "ou-engineering", "Name": "Engineering", "ParentId": "r-root"}],
            "Accounts": [{"Id": "000000000000", "Name": "Development", "ParentId": "ou-engineering"}],
            "SCPs": [
                {
                    "PolicyArn": "arn:aws:organizations::000000000000:policy/o-example/service_control_policy/scp-1",
                    "PolicyName": "DenyDataDelete",
                    "TargetIds": ["ou-engineering"],
                    "PolicyDocument": {
                        "Statement": [{"Effect": "Deny", "Action": "s3:DeleteObject", "Resource": "*"}]
                    },
                }
            ],
        },
    }

    result = build_coverage(inventory)

    node_types = {node["type"] for node in result["nodes"]}
    edge_types = {edge["type"] for edge in result["edges"]}
    assert {"resource", "resource_policy", "organization", "ou", "account", "scp"} <= node_types
    assert {"protects", "contains", "restricts"} <= edge_types
    assert result["coverage"]["resource_policies"] == 1
    assert result["coverage"]["scp_policies"] == 1


def test_coverage_graph_models_assumed_role_session():
    inventory = {
        "UserDetailList": [],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
        "Sessions": [
            {
                "SessionArn": "arn:aws:sts::000000000000:assumed-role/DataRole/analyst-session",
                "SourcePrincipal": "arn:aws:iam::000000000000:user/analyst",
                "RoleArn": "arn:aws:iam::000000000000:role/DataRole",
                "SessionPolicy": {"Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]},
            }
        ],
    }

    result = build_coverage(inventory)

    assert result["coverage"]["sessions"] == 1
    assert {edge["type"] for edge in result["edges"]} >= {"assumes", "has_session", "restricted_by"}
