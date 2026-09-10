import contextlib
import io
import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cy06 import __main__
from cy06.connector import EXPECTED_ROLE_ARN


class CliTests(unittest.TestCase):
    def test_profile_is_required(self):
        with self.assertRaises(SystemExit) as raised:
            __main__.main([])
        self.assertEqual(raised.exception.code, 2)

    @patch("cy06.__main__.summarize_inventory")
    @patch("cy06.__main__.load_inventory")
    def test_local_input_prints_import_summary(self, load_inventory, summarize_inventory):
        load_inventory.return_value = {"RoleDetailList": []}
        summarize_inventory.return_value = {
            "status": "ok",
            "users": 0,
            "groups": 0,
            "roles": 0,
            "policies": 0,
            "relationships": 0,
            "warnings": [],
        }
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(__main__.main(["--input", "inventory.json"]), 0)

        load_inventory.assert_called_once_with(Path("inventory.json"))
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ok")

    @patch("cy06.__main__.connect")
    def test_defaults_and_safe_json_output(self, connect):
        connect.return_value = SimpleNamespace(
            account_id="820919093456",
            source_arn="arn:aws:iam::820919093456:user/test",
            assumed_role_arn="arn:aws:sts::820919093456:assumed-role/r/s",
            expiration=datetime(2030, 1, 1, tzinfo=UTC),
            session=SimpleNamespace(secret="do-not-print"),
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(__main__.main(["--profile", "local"]), 0)

        connect.assert_called_once_with("local", EXPECTED_ROLE_ARN, "ap-south-1")
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["status"], "ok")
        self.assertEqual(output["expiration"], "2030-01-01T00:00:00+00:00")
        self.assertNotIn("session", output)
        self.assertNotIn("do-not-print", stdout.getvalue())

    @patch("cy06.__main__.connect", side_effect=ConnectionError("login incomplete"))
    def test_connection_error_is_concise_stderr_failure(self, connect):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(__main__.main(["--profile", "local"]), 1)
        self.assertEqual(stderr.getvalue(), "error: login incomplete\n")
        connect.assert_called_once()

    @patch("cy06.__main__.connect", side_effect=RuntimeError("secret runtime detail"))
    def test_unexpected_error_is_concise_stderr_failure(self, connect):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(__main__.main(["--profile", "local"]), 1)
        self.assertEqual(stderr.getvalue(), "error: unexpected connector failure\n")
        self.assertNotIn("secret runtime detail", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
