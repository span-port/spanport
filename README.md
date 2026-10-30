# Spanport

**Open-source, self-hosted LLM gateway and observability platform.** One trace answers: "this API took 4.2 s: 0.2 s in the database, 0.4 s in our code, 3.6 s in the Claude call, 2,300 tokens, ₹1.80."

Spanport sits between your apps and LLM providers (OpenAI, Anthropic, AWS Bedrock, Google Gemini), and collects your apps' requests, logs and errors, so cost, speed and failures are visible in one place. Everything runs in your own infrastructure. Free, no paid tier.

> **Status:** design complete for v1.0 (product, technical and business requirements, UI for every screen, database schema). Implementation is in progress, logs first. Working and tested today: log ingest through the OTel Collector, the Python and Node.js SDKs, log search, counts and live tail (API and UI), sign-in, and managing projects and keys from the UI. The LLM gateway, tracing, alerts and export come later.

## What it does

| Area | Highlights |
| --- | --- |
| **LLM gateway** | OpenAI- and Anthropic-compatible API for 4 providers; streaming; fallbacks and load balancing; cheaper-model routing; exact and semantic answer cache; stops generation when the caller disconnects |
| **Cost control** | Cost per request by client, project, key, model and end user; budgets that alert or block; month-end forecast; per-client invoice reports |
| **Keys and security** | LLM, data, browser and admin keys (shown once, stored hashed); rate limits; guardrails for personal data and prompt injection; audit log; Google sign-in and two-step codes; SSRF protection |
| **Monitoring** | Live and historical requests with a step-by-step waterfall; API speed (typical, slowest 5%, slowest 1%); 4xx and 5xx over time; grouped errors; logs with live tail and export; service map; deploy impact |
| **AI quality** | User feedback and automatic grading per prompt version |
| **Claude Code** | Cost and output per developer and per project, project members, optional prompt recording with consent |
| **Operations** | Alerts to email, Slack, Teams, PagerDuty, Opsgenie and webhooks; integrations with CloudWatch, Loki, Elasticsearch, S3, Kafka; storage management; backups; health and metrics |

## Quick start (everything in Docker)

Requirements: Docker with Compose v2.

```bash
git clone https://github.com/span-port/spanport && cd spanport
cp .env.example .env          # set the database passwords; provider keys are optional
docker compose up -d --build  # or: make up
```

| What | Where |
| --- | --- |
| Web UI | https://localhost (Caddy, local certificate) |
| API docs | https://localhost/api/docs |
| LLM gateway | https://localhost/v1 |
| Send traces, logs, metrics (OTLP) | `localhost:4317` (gRPC), `localhost:4318` (HTTP) |

On a server, set your domain in `.env`; Caddy obtains HTTPS certificates automatically (ports 80 and 443 open).

Containers when complete: `caddy`, `ui`, `server`, `gateway`, `collector`, `postgres`, `clickhouse`, `redis-state` (budgets, limits, sessions; never evicted), `redis-cache` (caches; least-recently-used eviction). For large installs, add Kafka.

**Today (pre-alpha)** the stack runs `ui`, `server`, `collector`, `postgres`, `clickhouse` and a one-off `migrate` job. The logs explorer is at `http://localhost:8080` (`SPANPORT_UI_PORT`).

**First sign-in.** While no user exists, the server logs a one-time setup token (single use, valid 1 hour):

```bash
docker compose logs server | grep setup_token
```

Open `http://localhost:8080/setup`, paste the token and create the Owner account. Typing an organization that already exists (e.g. `acme`) makes the Owner part of it, so its logs show up. Restart the server for a new token if it expired. Later sign-ins use email and password at `/login`; sessions end after 8 hours without activity. After 5 wrong passwords for one email within 15 minutes, that email can't sign in until the 15 minutes have passed (the page says how long). Forgotten password: `docker compose exec server python -m spanport_server.cli reset-password --email <email>` (signs that user out everywhere).

**Projects and keys from the UI.** Owners and admins add, rename, archive and restore projects under Setup → Clients and projects (any environment name, via "+ Environment"), and create, rename or revoke data and admin keys under Setup → API keys (a new key is shown once). Archiving a project stops its data keys at once and keeps its logs until they expire; an archived project can then be deleted for good (type its name to confirm), which removes its keys and all its logs. Revoked keys can be deleted from the list. The CLI commands below do the same from the server.

**Users and invites.** Owners and admins invite people under Setup → Users: enter an email and a role, then send the link that appears (it works once, for 7 days). Nobody gets access until the invited person opens the link, sees the email, organization and role it is for, and presses **Accept**; a mistyped invite can simply be cancelled. Owners and admins change roles and remove people (removed people are signed out everywhere and can be invited back). Only owners make or change owners, nobody changes their own role, and the organization always keeps an owner. Members and viewers can be limited to some projects (when inviting, or later with **Edit projects**): they then see only those projects' logs, alerts and rules, and other projects don't exist for them. Owners and admins always see every project.

**Log alerts.** Setup → Alerts (or **Create alert** on the Logs page, which carries the current search over) emails people when a search finds more than N lines in the last M minutes, for example more than 20 `level:ERROR` lines in 5 minutes; 0 means "any matching line". The form offers ready-made searches (Errors, Errors and warnings, Any log) and shows what the rule would say right now. Each rule is checked every minute; an alert emails once when it fires and once when it resolves itself, and people can mark it "I'm on it" or resolve it by hand. **Send test** checks every address before you rely on it. Emails carry counts and the search, never log lines. Set `SPANPORT_SMTP_HOST`, `SPANPORT_SMTP_FROM` and, if your server needs them, `SPANPORT_SMTP_USERNAME` / `SPANPORT_SMTP_PASSWORD` (see `.env.example`); without them rules can't be saved. Set `SPANPORT_UI_URL` (where people open the UI, e.g. `http://localhost:8080`) and alert emails get **Open alert** and **See matching logs** buttons. Owners and admins manage rules; members also acknowledge and resolve; viewers look.

Session cookies use the `__Host-` prefix, so browsers accept them only over HTTPS or on `http://localhost`.

Logs sent to the collector (OTLP on 4317 and 4318) with a data key are stored in ClickHouse for 7 days; traces (spans) sent the same way are stored for 30 days, each labelled as an LLM call, database call, outgoing call, incoming request or your own code. Monitor → **Requests** lists incoming requests (filter by time, route, slowness, errors) and opens each as a waterfall: the controller, service, database and outgoing calls nested, with each step's own time and a **See logs** link to the lines written during it. (The SDKs don't send traces yet; that comes next.) Create a data key with:

```bash
docker compose exec server python -m spanport_server.cli create-data-key \
  --org acme --client northwind --project hr-portal --environment production
```

The key is printed once. Apps send it as `Authorization: Bearer sp_ingest_...`.

**Search logs from scripts** with an admin key (organization-wide, scoped, expires within 90 days); the UI uses your session instead:

```bash
docker compose exec server python -m spanport_server.cli create-admin-key --org acme --scope logs:read --scope projects:read --expires-in-days 30
```

```bash
curl -X POST http://localhost:8000/api/v1/logs/search \
  -H "Authorization: Bearer sp_admin_..." -H "Content-Type: application/json" \
  -d '{"project_id": "...", "start": "2026-10-29T06:00:00Z", "end": "2026-10-29T07:00:00Z",
       "query": "level:ERROR (timeout OR deadlock) -healthcheck"}'
```

- `POST /api/v1/logs/search` returns `data`, `next_cursor` and `has_more`, newest first. Pass `cursor` to get the next page; `limit` is 1 to 500 (default 100).
- `POST /api/v1/logs/counts` takes the same filters and returns `total` and `by_level`.
- `POST /api/v1/logs/export` takes the same body plus `"format": "csv"` or `"ndjson"` and streams the matching lines as a file (newest first, ISO 8601 UTC times, at most 100,000 lines; more is refused with a hint to narrow the range). Viewers can't export. In the UI: Export → Download CSV / Download JSON lines on the Logs page.
- Filters: a text `query` (words, `"phrases"`, `field:value` with `*` wildcards, `OR`, `NOT`/`-`, brackets) and/or `filters` chips (`{"field": "level", "operator": "=", "value": "ERROR"}`; operators `=`, `!=`, `:` contains, `!:`), joined by `combine` (`and`/`or`). With `and` (what the UI sends), chips on the same field and operator are alternatives (`service = api` and `service = worker` means either) and different fields must all match. Field shortcuts: `ip` (`client.ip`), `user` (`user.id`), `trace`; any other name is looked up in the line's attributes, e.g. `order.id:1042`.
- Matching: `:` contains any part of the value, ignoring case; a plain word in `query` matches a whole word (`timeout` finds "request timeout", not "timeouts"); `*` is a wildcard. Search only sees text and fields that the app actually sent: a user written inside the message is found by text, not by `user:`.
- `POST /api/v1/logs/tail` takes the same filters without a range and streams new logs as server-sent events (`event: logs`, a JSON array per batch, oldest first), checking every 2 seconds.
- `GET /api/v1/projects` (scope `projects:read`) lists the organization's projects with their client and environment, using the same `limit`/`cursor` paging.
- The range must start within the last 7 days, and the project must belong to the caller's organization.
- The same endpoints accept a signed-in browser session; requests other than GET then need the `X-CSRF-Token` header (the value of the `__Host-sp_csrf` cookie).
- Alerts (signed-in session): `GET`/`POST /api/v1/alert-rules`, `PATCH`/`DELETE /api/v1/alert-rules/{id}`, `POST .../{id}/test`; `GET /api/v1/alert-events?project_id=...`, `POST /api/v1/alert-events/{id}/acknowledge` and `.../resolve`.
- Traces: `POST /api/v1/traces/search` (`project_id`, `start`, `end`, optional `service`, `route`, `min_duration_ms`, `errors_only`, `limit`, `cursor`) and `GET /api/v1/traces/{trace_id}?project_id=...`, with the same keys and sessions as log search.
- Users (owners and admins): `GET /api/v1/users`, `PATCH`/`DELETE /api/v1/users/{id}`, `PUT /api/v1/users/{id}/projects` (`{"all_projects": false, "project_ids": [...]}`); `GET`/`POST /api/v1/invites`, `DELETE /api/v1/invites/{id}`. Open to anyone with an invite link: `POST /api/v1/invites/inspect` and `POST /api/v1/invites/accept` (creates the account and signs in).
- Sign-in: `POST /api/v1/auth/setup` (setup token), `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.

**Manage keys:** `list-keys --org acme` shows every key's id, type, last four characters and status; `revoke-key --org acme --key-id <id>` stops a key on its next request.

## Development

Requirements: uv 0.13.1 or newer, Docker with Compose v2. Python 3.14 or 3.15.

```bash
uv sync                                                              # install dev tools
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build   # hot reload, databases on localhost
```

Checks (all must pass before a change is done):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy server/src server/tests
uv run pytest                                                        # unit tests; repository tests skip
uv run --env-file .env pytest                                        # also repository tests (dev stack up)
PYTHONPATH=server/src uv run lint-imports                            # layering
```

UI (Node 22.15+), in `ui/`:

```bash
npm ci
npm run dev                                   # http://localhost:5173, /api goes to the server in .env
npm run lint && npm run typecheck && npm test
```

Migrations: `python -m spanport_server.cli migrate` applies everything (the `migrate` job runs it on `docker compose up`). To undo the latest migration, use `rollback-postgres` or `rollback-clickhouse`, for example `docker compose exec server python -m spanport_server.cli rollback-postgres`.

On Kubernetes, the Helm chart in `deploy/helm/spanport` runs the same images.

## Connect an app

**Send logs** (Python 3.12+; see [sdk/python](sdk/python/README.md) for all options):

```python
pip install spanport

import spanport
spanport.init(data_key="sp_ingest_…", service="hr-portal-api")
# keep logging as usual; every logging call is sent to Spanport
```

**Send logs** (Node.js 22.15+; console, pino and winston; see [sdk/node](sdk/node/README.md)):

```js
npm install spanport

import * as spanport from "spanport";
spanport.init({ dataKey: "sp_ingest_…", service: "orders-api" });
// console.* is sent automatically; pino and winston write to spanport.logStream()
```

Request and database tracing come in a later release.

**Call models through the gateway**: point your OpenAI or Anthropic client at Spanport:

```python
client = OpenAI(base_url="https://spanport.yourco.com/v1", api_key="sp_sk_…")
```

**Claude Code**: commit `.claude/settings.json` in the repo (see `examples/claude-code/`) so usage is reported per project.

## Architecture

```
Apps (SDK) ──► OTel Collector ──► [Kafka, optional] ──► ClickHouse (telemetry)
Apps ──► Caddy ──► Gateway ──► OpenAI / Anthropic / Bedrock / Gemini
                    │
Browser ──► Caddy ──► UI ──► Server ──► PostgreSQL (settings)  ·  Redis state / cache
```

Gateway and server are separate Python (FastAPI) apps sharing `packages/core`; the UI is React and TypeScript. Each backend app follows controller → service → repository.

## Repository layout

| Path | Contents |
| --- | --- |
| `gateway/` | LLM gateway |
| `server/` | Management API, jobs, UI backend |
| `packages/core/` | Shared code: pagination, rate limiting, caching, settings, models |
| `ui/` | Web UI, one folder per page under `src/features/` |
| `sdk/python`, `sdk/node`, `sdk/browser` | SDKs |
| `db/` | PostgreSQL and ClickHouse schemas, tests, diagram (`spanport.dbml`) |
| `collector/` | OpenTelemetry Collector configurations |
| `deploy/` | Helm chart |
| `docs/` | PRD, TRD, BRD, ADRs, guides, engineering rules |
| `examples/` | Claude Code settings and SDK examples |

## Documentation

| Document | What it covers |
| --- | --- |
| [PRD](docs/product/prd.md) | What Spanport does and for whom: features, screens, UI and design rules |
| [TRD](docs/technical/trd.md) | How it is built: architecture, data stores, APIs, security, reliability, testing |
| [BRD](docs/business/brd.md) | Business goals, requirements BR-1 to BR-82, risks, milestones |
| [Database](db/README.md) | Every table, index, function and trigger |
| [Engineering rules](docs/engineering/rules.md) | Rules every change follows (also in `CLAUDE.md` for AI coding assistants) |
| [ADRs](docs/technical/decisions/) | Recorded technical decisions |

## Contributing

Read the [engineering rules](docs/engineering/rules.md) first. Use Conventional Commits, keep logic out of UI components and controllers, use the design tokens, and run `make test` before opening a pull request. Security issues: see `SECURITY.md`.

## License

Apache 2.0 (proposed; final choice between Apache 2.0 and MIT pending).