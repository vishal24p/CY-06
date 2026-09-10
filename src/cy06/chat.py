"""Read-only local tool loop for OpenAI-compatible chat providers."""

from __future__ import annotations

import json
import os
from ipaddress import ip_address
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .identity_security import IdentitySecurityError, IdentitySecurityTools

READ_ONLY_TOOL_NAMES = frozenset({
    "list_postgres_tables", "list_identity_entities", "get_identity_entity",
    "list_privilege_paths", "get_privilege_path", "list_security_findings",
    "list_remediation_plans", "list_audit_logs", "analyze_policy_impact",
    "verify_remediation",
})
MAX_TOOL_ROUNDS = 3
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 30
MAX_PROVIDER_TIMEOUT_SECONDS = 300
SYSTEM_INSTRUCTION = (
    "CY-06 uses only the fixed read-only tool registry. Never import, simulate, "
    "apply, approve, or otherwise mutate data."
)


class ChatError(ValueError):
    """Safe error returned when chat cannot complete."""


_FUNCTIONS = {
    "list_postgres_tables": {},
    "list_identity_entities": {"search": {"type": "string"}, "entity_type": {"type": "string"}, "sort_by": {"type": "string", "enum": ["name", "type"]}, "limit": {"type": "integer"}, "offset": {"type": "integer"}},
    "get_identity_entity": {"entity_id": {"type": "string"}},
    "list_privilege_paths": {"risk": {"type": "string"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}},
    "get_privilege_path": {"path_id": {"type": "string"}},
    "list_security_findings": {"status": {"type": "string"}, "risk": {"type": "string"}},
    "list_remediation_plans": {"status": {"type": "string"}},
    "list_audit_logs": {"limit": {"type": "integer"}},
    "analyze_policy_impact": {"policy_id": {"type": "string"}},
    "verify_remediation": {"plan_id": {"type": "string"}},
}
_REQUIRED = {"get_identity_entity": ["entity_id"], "get_privilege_path": ["path_id"], "analyze_policy_impact": ["policy_id"], "verify_remediation": ["plan_id"]}
_TOOLS = [
    {"type": "function", "function": {"name": name, "description": f"Read local identity-security data with {name}.", "parameters": {"type": "object", "properties": properties, "required": _REQUIRED.get(name, []), "additionalProperties": False}}}
    for name, properties in _FUNCTIONS.items()
]


def _dispatch(name: str, arguments: dict[str, Any], tools: IdentitySecurityTools) -> Any:
    if name not in READ_ONLY_TOOL_NAMES:
        raise ChatError("Requested tool is not available to chat")
    _validate_tool_arguments(name, arguments)
    try:
        method = getattr(tools, name)
        return method(**arguments)
    except IdentitySecurityError as error:
        raise ChatError(str(error)) from error
    except Exception as error:
        raise ChatError("Local tool failed") from error


def run_chat(
    messages: list[dict[str, str]],
    *,
    open_url: Callable[..., Any] = urlopen,
    tools_factory: Callable[[], IdentitySecurityTools] = IdentitySecurityTools,
) -> dict[str, Any]:
    """Send chat messages to a configured provider and execute read-only calls."""
    base_url = _provider_base_url(_required_environment("CY06_CHAT_BASE_URL"))
    model = _required_environment("CY06_CHAT_MODEL")
    timeout_seconds = _provider_timeout_seconds()
    if not isinstance(messages, list) or len(messages) > 20:
        raise ChatError("messages must contain at most 20 items")
    if not all(isinstance(message, dict) and isinstance(message.get("role"), str) and isinstance(message.get("content"), str) for message in messages):
        raise ChatError("messages must contain role and content strings")
    if any(message["role"] not in {"user", "assistant"} for message in messages):
        raise ChatError("messages must use user or assistant roles")
    if any(not 1 <= len(message["content"]) <= 4000 or not message["content"].strip() for message in messages):
        raise ChatError("message content must be between 1 and 4000 non-blank characters")

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    request_messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_INSTRUCTION}, *messages]
    completed: list[dict[str, str]] = []
    tools: IdentitySecurityTools | None = None
    for _ in range(MAX_TOOL_ROUNDS):
        message = _provider_message(endpoint, model, request_messages, open_url, timeout_seconds)
        tool_calls = _tool_calls(message)
        if not tool_calls:
            content = message.get("content")
            if not isinstance(content, str) or not 1 <= len(content) <= 4000 or not content.strip():
                raise ChatError("Provider response was invalid")
            return {"message": content, "tool_calls": completed}
        request_messages.append({**message, "role": "assistant"})
        tools = tools or tools_factory()
        for call_id, name, arguments in tool_calls:
            result = _dispatch(name, arguments, tools)
            request_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, default=str)})
            completed.append({"name": name, "status": "completed"})
    raise ChatError("Chat tool-call limit reached")


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ChatError(f"{name} is required")
    return value


def _provider_timeout_seconds() -> int:
    value = os.environ.get("CY06_CHAT_TIMEOUT_SECONDS", str(DEFAULT_PROVIDER_TIMEOUT_SECONDS)).strip()
    try:
        timeout_seconds = int(value)
    except ValueError as error:
        raise ChatError("CY06_CHAT_TIMEOUT_SECONDS must be an integer between 1 and 300") from error
    if not 1 <= timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS:
        raise ChatError("CY06_CHAT_TIMEOUT_SECONDS must be an integer between 1 and 300")
    return timeout_seconds


def _provider_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
    except ValueError as error:
        raise ChatError("CY06_CHAT_BASE_URL must use HTTPS or local HTTP and end in /v1") from error
    if not host or not parsed.path.endswith("/v1") or parsed.query or parsed.fragment:
        raise ChatError("CY06_CHAT_BASE_URL must use HTTPS or local HTTP and end in /v1")
    if parsed.scheme == "https" or parsed.scheme == "http" and _is_local_host(host):
        return value
    raise ChatError("CY06_CHAT_BASE_URL must use HTTPS or local HTTP and end in /v1")


def _is_local_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _validate_tool_arguments(name: str, arguments: dict[str, Any]) -> None:
    properties = _FUNCTIONS[name]
    if set(arguments) - set(properties) or any(key not in arguments for key in _REQUIRED.get(name, [])):
        raise ChatError("Tool arguments are invalid")
    for key, value in arguments.items():
        schema = properties[key]
        if schema["type"] == "string":
            valid = isinstance(value, str)
        else:
            valid = isinstance(value, int) and not isinstance(value, bool)
            if key == "limit":
                valid = valid and 1 <= value <= 200
            elif key == "offset":
                valid = valid and value >= 0
        if not valid or value not in schema.get("enum", [value]):
            raise ChatError("Tool arguments are invalid")


def _provider_message(endpoint: str, model: str, messages: list[dict[str, Any]], open_url: Callable[..., Any], timeout_seconds: int) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key := os.environ.get("CY06_CHAT_API_KEY"):
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = Request(endpoint, data=json.dumps({"model": model, "messages": messages, "tools": _TOOLS}).encode(), headers=headers, method="POST")
        with open_url(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read())
    except (HTTPError, URLError, OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as error:
        raise ChatError("Provider request failed") from error
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise ChatError("Provider response was invalid") from error
    if not isinstance(message, dict):
        raise ChatError("Provider response was invalid")
    return message


def _tool_calls(message: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    calls = message.get("tool_calls", [])
    if calls is None:
        return []
    if not isinstance(calls, list):
        raise ChatError("Provider response was invalid")
    parsed = []
    for call in calls:
        try:
            call_id, function = call["id"], call["function"]
            name, encoded = function["name"], function["arguments"]
        except (KeyError, TypeError) as error:
            raise ChatError("Provider response was invalid") from error
        if not isinstance(call_id, str) or not isinstance(name, str) or not isinstance(encoded, str):
            raise ChatError("Provider response was invalid")
        try:
            arguments = json.loads(encoded)
        except json.JSONDecodeError as error:
            raise ChatError("Tool arguments must be valid JSON") from error
        if not isinstance(arguments, dict):
            raise ChatError("Tool arguments must be an object")
        parsed.append((call_id, name, arguments))
    return parsed
