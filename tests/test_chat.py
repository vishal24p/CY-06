import json
from contextlib import contextmanager

import pytest

from cy06.chat import ChatError, READ_ONLY_TOOL_NAMES, run_chat


class FakeTools:
    def list_security_findings(self):
        return [{"title": "No critical findings."}]


def tool_call_then_reply(name):
    return [
        {
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call-1", "type": "function", "function": {"name": name, "arguments": "{}"},
            }]}}],
        },
        {"choices": [{"message": {"content": "No critical findings."}}]},
    ]


def fake_urlopen(responses):
    responses = iter(responses)

    @contextmanager
    def open_url(request, timeout):
        assert timeout == 30
        yield type("Response", (), {"read": lambda self: json.dumps(next(responses)).encode()})()

    return open_url


def test_chat_rejects_missing_provider_configuration(monkeypatch):
    for name in ("CY06_CHAT_BASE_URL", "CY06_CHAT_MODEL", "CY06_CHAT_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ChatError, match="CY06_CHAT_BASE_URL"):
        run_chat([{"role": "user", "content": "List findings"}])


def test_chat_registry_never_exposes_mutation_tools():
    assert "list_security_findings" in READ_ONLY_TOOL_NAMES
    blocked = {"initialize", "import_inventory", "simulate_remediation", "apply_remediation", "mark_finding_resolved"}
    assert blocked.isdisjoint(READ_ONLY_TOOL_NAMES)


def test_chat_dispatches_an_allowed_tool(monkeypatch):
    monkeypatch.setenv("CY06_CHAT_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("CY06_CHAT_MODEL", "llama3")

    result = run_chat(
        [{"role": "user", "content": "Show findings"}],
        open_url=fake_urlopen(tool_call_then_reply("list_security_findings")),
        tools_factory=FakeTools,
    )

    assert result["message"] == "No critical findings."
    assert result["tool_calls"] == [{"name": "list_security_findings", "status": "completed"}]


def test_chat_rejects_provider_requested_mutation(monkeypatch):
    monkeypatch.setenv("CY06_CHAT_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("CY06_CHAT_MODEL", "llama3")

    with pytest.raises(ChatError, match="not available"):
        run_chat(
            [{"role": "user", "content": "Apply it"}],
            open_url=fake_urlopen(tool_call_then_reply("apply_remediation")),
            tools_factory=FakeTools,
        )


def test_chat_returns_tool_results_with_an_assistant_message(monkeypatch):
    monkeypatch.setenv("CY06_CHAT_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("CY06_CHAT_MODEL", "llama3")
    requests = []
    responses = iter(tool_call_then_reply("list_security_findings"))

    @contextmanager
    def open_url(request, timeout):
        requests.append(json.loads(request.data))
        yield type("Response", (), {"read": lambda self: json.dumps(next(responses)).encode()})()

    run_chat([{"role": "user", "content": "Show findings"}], open_url=open_url, tools_factory=FakeTools)

    assert requests[1]["messages"][-2]["role"] == "assistant"
    assert requests[1]["messages"][-1]["tool_call_id"] == "call-1"


def test_chat_normalizes_an_unavailable_allowed_tool_implementation(monkeypatch):
    monkeypatch.setenv("CY06_CHAT_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("CY06_CHAT_MODEL", "llama3")

    with pytest.raises(ChatError, match="list_audit_logs"):
        run_chat(
            [{"role": "user", "content": "Show audit logs"}],
            open_url=fake_urlopen(tool_call_then_reply("list_audit_logs")),
            tools_factory=FakeTools,
        )
