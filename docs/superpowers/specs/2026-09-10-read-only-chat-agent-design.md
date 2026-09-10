# Read-only chat agent design

## Goal

Add a chat panel that lets a user ask questions about the local identity-security database. The agent may use only existing read-only `IdentitySecurityTools` methods. It must never offer or invoke an import, simulation, approval, or other mutation.

## Scope

The backend adds `POST /api/v1/chat`. It accepts a bounded list of prior chat messages and returns one completed assistant reply plus any tool calls made while producing it. Streaming, saved conversations, file uploads, and provider-specific UI are out of scope.

The existing mutation methods remain in `IdentitySecurityTools` unchanged:

- `initialize`
- `import_inventory`
- `simulate_remediation`
- `apply_remediation`
- `mark_finding_resolved`

They are absent from the chat tool registry. The registry contains only `list_postgres_tables`, `list_identity_entities`, `get_identity_entity`, `list_privilege_paths`, `get_privilege_path`, `list_security_findings`, `list_remediation_plans`, `list_audit_logs`, `analyze_policy_impact`, and `verify_remediation`.

## Provider configuration

The API calls an OpenAI-compatible Chat Completions endpoint over HTTPS or a local HTTP endpoint. Configuration is read only from process environment:

- `CY06_CHAT_BASE_URL`: provider base URL ending in `/v1`; required.
- `CY06_CHAT_MODEL`: provider model identifier; required.
- `CY06_CHAT_API_KEY`: provider API key; optional for local providers such as Ollama.

This supports OpenAI, OpenRouter, Ollama, and compatible services without provider-specific code. Values are never returned by the API, logged, or committed. Missing configuration or database connectivity returns a concise actionable error.

Messages and tool results are sent to the configured provider. A local Ollama endpoint keeps this processing local; a remote provider does not.

## Backend flow

1. Validate message count, role, text length, and supported tool-call arguments.
2. Build the model request from conversation history, a read-only system instruction, and the fixed tool definitions.
3. Send it to the configured provider.
4. Dispatch only a model-requested tool whose name is in the fixed registry. Construct `IdentitySecurityTools` with its existing database configuration and call that method.
5. Return the tool result to the model. Repeat for a small fixed number of rounds, then return the final assistant text and tool activity.
6. Return an error rather than guessing if the model gives an invalid tool call, database access fails, provider access fails, or the round limit is reached.

The server, rather than the model prompt, is the permission boundary. A prompt injection cannot add a method to the registry.

## UI

Add a focused native React/Tailwind `ChatPanel` beside the analysis workspace. It contains:

- a scrollable message thread with semantic user and assistant messages;
- visible, concise status for each read-only tool call;
- accessible textarea, send button, loading state, and error state;
- responsive single-column placement on small screens.

No chat component framework is added. The app already has React and Tailwind; native components avoid an AI-SDK and component-library dependency tree while matching its existing visual language.

## Tests and verification

Backend tests cover configuration errors, rejected malformed messages, the read-only registry, dispatch of an allowed tool, and attempted dispatch of a mutation. They mock the provider transport and database-backed tools; no network call or provider key is required.

Run the Python test suite, frontend lint, frontend production build, and a frontend type check through the build. Manually verify keyboard submission, disabled-send behavior, errors, and mobile layout.
