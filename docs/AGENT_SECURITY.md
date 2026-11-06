# Stage 4 security boundary

The agent is strictly read-only. The registry contains no writes, workflow execution,
task creation/assignment, supplier updates, invoice approval, inventory changes,
deletion, external messaging, browsing, arbitrary HTTP, raw SQL, shell, Python or
arbitrary filesystem access. Unknown tools and extra/invalid arguments are rejected
in server code independently of model behavior. No source can extend the registry.

`scripts.prepare_agent_reader` explicitly provisions the project-specific
`opspilot_agent_reader` NOLOGIN/NOINHERIT/NOSUPERUSER role. It grants schema USAGE
and SELECT on known business/retrieval tables only. The command is restricted to
OpsPilot and UUID-isolated test database names and refuses an unexpectedly privileged
existing role. Each agent tool transaction sets `REPEATABLE READ, READ ONLY`, switches
to this fixed role and applies a local statement timeout; rollback restores pooled
connection state. Tests verify missing INSERT/UPDATE/DELETE/TRUNCATE privileges and
rejected writes. No model argument can select a role or execute session SQL.

This is role isolation within the existing trusted server connection pool. Other
Stage 1–3 maintenance still uses the demonstration owner connection. It is not a
claim that the whole application has separate production credentials or that server
code compromise could not escape the trusted boundary. Stage 5 authentication/RBAC
and deployment-level least privilege are not implemented.

All user context, retained history, names, incident/task strings, document excerpts
and tool payloads are data. Trusted instructions consist only of the fixed server
prompt and validated cutoff. Provider outputs retain their proper protocol roles;
tool results are supplied exclusively as untrusted function results: normalized
`function_call_output`, translated to native `role=tool` for Ollama. Source strings
cannot authorize actions, alter provider settings, change requested filters, disable
source checks or request secrets. The model may still be influenced semantically;
the deterministic execution and evidence boundary does not depend on it politely refusing.

Negative tests cover unregistered write/code/file/web tools, malformed/duplicate JSON,
invalid IDs/filters, excessive counts, fabricated evidence/citations/numbers, false
action completion claims, context/tool/round limits, actual malicious task/incident
text and malicious temporarily indexed Markdown. Document passages remain quoted
data and never become privileged instructions. Model-independent boundary tests
are not a live-model prompt-injection robustness score or a claim of immunity.

The primary Ollama adapter accepts only local HTTP hosts, disables proxies/redirects,
requires downloaded GGUF/tool metadata, rejects cloud aliases and uses no API key.
The startup helper disables cloud features in its own process. The OpenAI adapter
is instantiated only after explicit provider selection, never as a fallback.

Optional OpenAI API keys are SecretStr configuration, never database rows, committed files,
tool arguments or business evidence. The official API endpoint is fixed; arbitrary
provider URLs are not accepted. No raw provider messages, secret-bearing prompts or
reasoning are stored in an audit ledger. Responses/traces contain selected metadata,
validated arguments, timing and usage; invalid argument bodies are not echoed.
Opaque conversation IDs and bounded memory are suitable only for the single-user
localhost demo. There is no authentication, tenant separation, durable audit service,
approval engine, production rate limiting or frontend.

## Stage 4B enforcement

Preflight grammar improves clear write/execute/secret/send refusals; explanatory
examples and informational procedures stay eligible. It is not a complete intent
classifier or the security boundary. The seventeen-tool allowlist and read-only
transactions still prevent actions regardless of model/retrieved instructions.
Capability selection exposes registered tools only and adds no authorization.

Correction feedback contains sanitized field paths/types, no rejected values.
Repeated failed calls are suppressed; one corrected attempt per tool is allowed.
Failed retrieval cannot masquerade as data absence. Candidate subject/relationship/
prose checks add rejection conditions without relaxing numeric, citation, source-hash
or effective-date validation. All prior and new security checks passed within the
348-test regression, not a live-model immunity score. See [report](STAGE4B_REPORT.md).
