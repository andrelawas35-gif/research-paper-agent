# Post-Deployment Surface Recovery Runbook

Use this runbook after a deploy or local environment change to confirm that the
PKM PWA, FastAPI service, ADK Web/CLI, and optional Discord launcher still use
the intended configuration. It is an operational reference for skills and
maintainers; it does not change the release scope in ADR 0139.

## Surface map

| Surface | Local command / address | Required configuration |
| --- | --- | --- |
| PKM API | `uvicorn agent_runtime.asgi:create_local_app --factory --host 127.0.0.1 --port 8001` | `.env`, `PKM_API_KEY_HASH`, local file record keys |
| PWA | `cd frontend && npm run dev` at `http://127.0.0.1:5173` | Proxies `/api` and `/health` to port 8001 by default |
| ADK Web | `.venv/bin/adk web .` at `http://127.0.0.1:8000/dev-ui/` | `.env`, including OpenAI configuration; use `--port 8002` if 8000 is occupied |
| ADK CLI | From the parent directory: `research_paper_agent/.venv/bin/adk run research_paper_agent` | Same project `.env` and agent tool registry |
| Discord (optional local launcher) | From the parent directory: `research_paper_agent/.venv/bin/python -m research_paper_agent.discord_bot` | `DISCORD_BOT_TOKEN`, optional `DISCORD_USER_ID`, same project `.env` |

Do not bind the local API and ADK Web to the same port. Port 8000 is reserved
for ADK Web locally; port 8001 is the local FastAPI service. Production routing
is different: Caddy fronts the deployed API, and `create_production_app` retains
OCI-backed per-record key custody.

## Post-deployment checks

From the project directory, with the API, PWA, and ADK Web processes running:

```bash
curl -fsS http://127.0.0.1:8001/health/ready
curl -fsS http://127.0.0.1:5173/health/ready
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/dev-ui/
```

The first two commands must return a ready health payload; the last must return
`200`. In the PWA, unlock and visit a route that performs an API request. The
banner `Some local services are unavailable` must not appear.

For agent surfaces, start a fresh ADK Web session and run a normal agent query
through both ADK Web and `adk run`. For an explicit external lookup (for
example, “search the web for current papers on retrieval-augmented generation”),
confirm that `search_web` is available rather than receiving a tool-not-found
error. Restart ADK Web or the CLI session after code or environment changes;
an existing session does not reload the agent's tool registry.

For Discord, verify that the launcher reaches its `Research Paper Agent Discord
bot starting...` message and that one authorized test message receives a reply.
Do not describe Discord as production-ready: ADR 0139 keeps Discord, reminders,
and the background dispatcher outside the first approved daily-use scope.

## Common failures and recovery

| Symptom | Likely cause | Recovery |
| --- | --- | --- |
| ADK Web at port 8000 serves another project or cannot start | Another local ADK server already owns port 8000 | Do not stop the unrelated service. Start this project with `.venv/bin/adk web . --host 127.0.0.1 --port 8002`, then open `http://127.0.0.1:8002/dev-ui/`. |
| PWA reports unavailable local services or `/health/ready` returns 404 | Vite is proxying to ADK Web on 8000, or the local API is not running | Start `create_local_app` on 8001. Keep `VITE_API_TARGET` at `http://localhost:8001` unless deliberately overriding it, then restart Vite. |
| ADK Web opens but a request says `Tool 'search_web' not found` | An old server/session has an older filtered tool tier, or the query was not classified as external lookup | Restart ADK Web and start a fresh session. Use explicit external-lookup wording; those queries must select the balanced tier that includes `search_web`. |
| Local API fails because OCI record-key settings are absent | The production factory was used for local development | Use `agent_runtime.asgi:create_local_app`; it is the local-only factory and uses file-backed record keys under `PKM_DATA_DIR`. |
| Production API uses file record keys or accepts missing OCI settings | The local factory was used in deployment, or OCI environment settings are incomplete | Deploy `create_production_app` only. Follow `ORACLE_VM_SETUP.md`; production must fail closed if OCI record-key custody is unavailable. |
| CLI or Discord cannot authenticate to OpenAI | `.env` was not loaded or `OPENAI_API_KEY` / model variables are missing | Restore the project `.env` from secure deployment configuration, then start a new CLI, ADK Web, or Discord process. Never put credentials in Git, chat, or command history. |
| Discord exits immediately | `DISCORD_BOT_TOKEN` is missing or invalid | Set the token in the project `.env`, then restart the module command from the parent directory. |

## Evidence to record

For a deployment or recovery, record the date, release identifier, the three
health-check results, the ADK Web and CLI query outcome, and any Discord test
outcome. Keep personal message content and credentials out of logs. For the
full private-PWA launch gates and recovery requirements, use
[`docs/launch-readiness.md`](launch-readiness.md).
