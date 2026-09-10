import json

import pytest

from cy06.inventory import InventoryError, load_inventory, summarize_inventory


def test_load_and_summarize_iam_inventory(tmp_path):
    payload = {
        "UserDetailList": [
            {
                "UserName": "analyst",
                "GroupList": [],
                "AttachedManagedPolicies": [],
                "UserPolicyList": [{"PolicyName": "AssumeDeploymentRole"}],
            }
        ],
        "GroupDetailList": [],
        "RoleDetailList": [
            {
                "RoleName": "DeploymentRole",
                "AttachedManagedPolicies": [{"PolicyName": "AdministratorAccess"}],
                "RolePolicyList": [],
                "InstanceProfileList": [],
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "analyst",
                            "Action": "sts:AssumeRole",
                        }
                    ]
                },
            }
        ],
        "Policies": [{"PolicyName": "AdministratorAccess"}],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    summary = summarize_inventory(load_inventory(path))

    assert summary == {
        "status": "ok",
        "users": 1,
        "groups": 0,
        "roles": 1,
        "policies": 1,
        "relationships": 3,
        "warnings": [],
    }


def test_invalid_json_has_concise_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(InventoryError, match="invalid JSON"):
        load_inventory(path)


def test_non_list_aws_section_is_rejected(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"RoleDetailList": {}}), encoding="utf-8")

    with pytest.raises(InventoryError, match="RoleDetailList must be a list"):
        load_inventory(path)
