# CLAUDE.md

Spanport is an open-source, self-hosted LLM gateway and observability platform (logs, traces, API metrics, LLM cost). It's pre-alpha, and the code is being written now.

The source of truth is [docs/product/prd.md](docs/product/prd.md) (what), [docs/technical/trd.md](docs/technical/trd.md) (how) and [docs/business/brd.md](docs/business/brd.md) (why). The rules every change follows are in [docs/engineering/rules.md](docs/engineering/rules.md). Read the relevant section before building a feature. Where the docs and this file disagree, this file wins.

## Hard rules (never break)

- **Never read `.env` files** or any file holding secrets: no `cat`, `type`, `Get-Content`, `grep`, editor read, script or any other way. If a value is needed, ask the user. To show which variables exist, use `.env.example`.
- **Never commit.** No `git commit`, `git push` or any other git write. The user commits.
- **No destructive commands without asking**: dropping or truncating tables, `docker volume rm`, deleting files or folders, resetting databases.
- **Every migration is reversible.** Each Alembic migration has a working `downgrade()`; each ClickHouse migration has a `down.sql`.
- **Schema changes only through migrations.** No auto-sync: no `synchronize: true`, no SQLAlchemy `metadata.create_all()` in app code.
- **Pin exact versions for every package.** Python uses `==` (no `>=`, `~=` or `^`) and `uv.lock` pins every transitive dependency. `package.json` uses no `^` or `~`. Docker images use exact tags.
  - **Exception: published libraries (the SDKs).** Their *runtime* dependencies declare ranges, e.g. `opentelemetry-sdk>=1.45.1,<2`, so they install alongside any app's own dependencies. The lower bound is the vetted version. Their dev dependencies are still pinned with `==`, and `uv.lock` still pins everything for our own dev and test runs.
- **Vet every new or upgraded package.** Check its version and known vulnerabilities at https://app.in.flyingduck.io/packages before adding it, and say what you found. If you can't open the site, stop and ask the user to check. Never skip the check.
- **Ask before adding any new dependency.** Don't add one when the stdlib or an existing dependency covers the need.

## Code quality rules

Full detail in [docs/engineering/rules.md](docs/engineering/rules.md). The ones that matter most:

- **No complex code.** Use small functions and early returns. No clever one-liners and no abstraction without a second use. No file over about 300 lines and no function over about 50 lines without a reason.
- **Every name has a meaning.** Variables, functions and files say what they hold or do (`expired_keys`, not `data`, `tmp` or `x`). The only exception is a loop index. Naming conventions are in rules.md section 4.
- **Constants live in one place.** Each app's constants go in its `core/constants.py`, shared ones in `packages/core/spanport_core/constants.py`, the SDK's in `_constants.py` and UI constants in `ui/src/constants/`. Code refers to them by name, with no magic numbers or strings inline. This includes limits, header names, separators, regex patterns, file names and paths. Lookup tables that only pair enums are written as functions (`match`) instead. Two exceptions: values computed from code (e.g. column names derived from a dataclass's fields) stay next to that code, and test files keep their own sample data.
- **Reuse common components.** Before writing a helper, UI component, schema or query, search `packages/core`, `ui/src/lib` and `ui/src/components/ui` and extend what's there. Code used by both gateway and server goes in `packages/core`.
- **Document every service and controller.** Each function has a docstring (or TSDoc in TypeScript) saying what it does, its inputs and what it returns or raises. Non-obvious logic gets a short inline comment explaining why.
- **No `ponytail:` comments**, commented-out code, dead code or TODO stubs.
- **Every feature has unit tests**, in the same change as the feature.
- **Every backend call logs one meaningful line.** Say what happened and with what context, for example `log search project=hr-portal range=1h filters=2 rows=500 duration_ms=84`, or `ingest rejected: revoked data key ...a1b2 project=hr-portal`. Logs are NDJSON to stdout with `ts`, `level`, `message`, `service`, `trace_id`, `span_id`. Never log "here", "inside function", "success" or a full object dump. Never log secrets, keys, passwords or prompt bodies. Use the logger from `core/logging`, never `print` or `console.log`.
- **Errors are never swallowed.** Catch only what you can handle. API errors are RFC 9457 problem details (`application/problem+json`) with `type`, `title`, `status`, `detail`, a stable `code` and `request_id`. Never a stack trace.
- **Config comes from environment variables through `core/config`** (pydantic-settings, validated at start-up). Env vars start with `SPANPORT_` except standard ones like `DATABASE_URL`. No hardcoded URLs, ports or credentials. Keep `.env.example` up to date with every variable, using placeholder values only.
- **Checks must pass**: ruff (lint and format), mypy and import-linter for Python; eslint and `tsc` in strict mode for TypeScript. CI (GitHub Actions) runs them once the workflow exists; until then, and always before saying a step is done, run them locally.
- **No em dashes** in code, UI text, docs or commit messages.

## Working rules

- Before each step, explain the plan: which files you'll create or change, and why. After each step, summarise what changed, what was tested and what was skipped.
- Change the PRD, TRD and BRD only when the user asks. Update the README and the other docs when behaviour changes.
- If a rule here blocks the task, stop and ask. Don't work around it.

## Build order

The build order is **logs first, then LLM**, which differs from the PRD's order.

1. Foundation: monorepo skeleton, Docker Compose (Postgres, ClickHouse, OTel Collector, server), server skeleton with `/health` *(done)*
2. Log ingest: orgs, clients, projects and data keys in Postgres; the ClickHouse `logs` table; `POST /v1/logs`; a CLI command to create a data key *(done)*
3. Python SDK: `spanport.init(data_key=..., service=...)`, a `logging` hook, trace_id/span_id on each log, a data key check at start-up (`GET /api/v1/api-keys/current`); collector gRPC receiver *(done)*
4. Node.js SDK: the same features as the Python SDK *(done)*
5. Logs query API: filter chips and the text query compiled to parameterized ClickHouse SQL; admin keys *(done)*
6. UI logs explorer: project switcher, time picker (UTC default), filter bar, live tail
7. Auth (setup link, login, roles), export, log alerts *(done: sign-in, users and invites, per-project access, login rate limit, log alerts by email, export up to 100k lines)*
8. Then the LLM work in the PRD's order: gateway core, streaming and cost, tracing and API monitoring, security, LLM debugging and Claude Code analytics

Build only the current step. Don't scaffold for later steps.

### Pending: verified package releases (remind the user once the build order is done)

The Python SDK (`spanport` on PyPI, 0.1.0 and 0.1.1) was uploaded from a laptop with an API token, so PyPI shows "No provenance found". Releases should instead be published by GitHub Actions with Trusted Publishing, which adds Sigstore provenance (attestations). Same later for the Node SDK on npm (`npm publish --provenance`).

1. The user pushes the repo to GitHub (`span-port/spanport`) and yanks `spanport` 0.1.0 on PyPI (key-check redirect bug, fixed in 0.1.1).
2. pypi.org → spanport → Manage → Publishing → add a GitHub trusted publisher: owner `span-port`, repo `spanport`, workflow `release-python-sdk.yml`, environment `pypi`.
3. Add `.github/workflows/release-python-sdk.yml`: on tag `sdk-python-v*`, run ruff, mypy and tests (Python 3.12 and 3.14), `uv build`, then publish with `pypa/gh-action-pypi-publish` (no token). Vet `actions/checkout`, `astral-sh/setup-uv` and `pypa/gh-action-pypi-publish` first and pin each to a commit SHA.
4. The user deletes the PyPI API tokens.
5. Add `SECURITY.md` (how to report a vulnerability), 2FA on GitHub and PyPI for everyone with access, and branch protection on `main`.

## Scope rules

- **No Terraform.** Deployment is Docker Compose and Helm only.
- **No Kafka for now.** The collector batches; the server inserts each request with ClickHouse async inserts (`async_insert=1, wait_for_async_insert=1`) and replies only after the data is on disk. It returns `503` when ClickHouse is down, so the collector retries. No server-side buffer. Add the optional Kafka profile only when load tests show it's needed. Kafka integrations (forwarding and pulling) come later with the other integrations.
- Deferred until logs work end to end: integrations (CloudWatch, Loki, ELK, S3, Kafka), background exports over 100k lines, SSO, and search in place.

## Stack

| Part | Choice |
| --- | --- |
| Gateway, server, Python SDK | Python 3.14 to 3.15 supported (Docker runs 3.14.8); ruff and mypy target 3.14. FastAPI, Pydantic, httpx |
| Python packaging | uv 0.13.1 (`pyproject.toml` + `uv.lock`). No pip or requirements files. Run tools with `uv run …` |
| Docker | One `docker-compose.yml` at the repo root runs the whole stack; `docker-compose.dev.yml` adds hot reload and database ports. Images are built from the repo root (so `packages/core` is included), use `python:3.14.8-slim`, run as a non-root user and have a `HEALTHCHECK` in the Dockerfile. Keep Dockerfiles plain: one stage, copy uv in, `uv sync --frozen --no-dev` |
| UI, Node SDK | TypeScript; React + Vite for the UI. TanStack Query for server data, URL search params for filters, one small Zustand store, React Hook Form + zod |
| Postgres | SQLAlchemy 2.1 async + asyncpg, Alembic migrations in `db/postgres/migrations/`. Primary keys are UUIDv7 (`uuid.uuid7`); every foreign key has an index |
| ClickHouse | clickhouse-connect (async), hand-written parameterized SQL, no ORM. Migrations are `db/clickhouse/migrations/<NNNN_name>/up.sql` + `down.sql` |
| Redis | redis-py asyncio (needed from the gateway step onwards). Keys are `sp:<area>:<...>` |
| Telemetry | OpenTelemetry (OTLP) |

## Code structure (mandatory)

The repo layout is in [docs/engineering/rules.md](docs/engineering/rules.md) section 1. Create a folder only when the current step needs it.

```
packages/core/src/spanport_core/   shared Python code (pagination, rate limits, cache, URL guard, errors, settings base, time helpers)
gateway/src/spanport_gateway/      the LLM gateway
server/src/spanport_server/        the API server, jobs and CLI
ui/src/                            the web app
sdk/{python,node,browser}/         SDKs
db/{postgres,clickhouse}/          migrations and schema
collector/  deploy/  docs/  tests/{e2e,load}/
```

The gateway and server always use controller → service → repository layering, even when a flatter layout would be shorter. One file per feature per layer:

```
controllers/   HTTP only: routes, validation, auth, calls one service. No SQL, Redis or business rules
services/      business rules. Never imports FastAPI, never writes SQL
repositories/  data access only, split into postgres/, clickhouse/, redis/. No business decisions
clients/       calls to outside systems (LLM providers, email, Slack)
schemas/       Pydantic request/response models
cli/           admin commands; call services like controllers do
jobs/          scheduled tasks that call services, never repositories
core/          config, constants, errors, logging
dependencies.py  wiring via FastAPI Depends
```

SQLAlchemy models live in `server/src/spanport_server/models/`, separate from schemas. They move to `packages/core` when the gateway needs them.

- Calls only go downward: controller → service → repository or client. import-linter enforces it.
- Services depend on repository `Protocol`s, so tests can use in-memory fakes.
- UI: one folder per screen area in `ui/src/features/<feature>/` (`components/`, `hooks/`, `api.ts`, `index.ts`); shared parts in `components/ui/`, pure helpers in `lib/`, the HTTP client in `api/`. Components only display; logic lives in hooks and `lib`. No `fetch` in components.

## API

- Management API under `/api/v1/` with plural kebab-case nouns (`/api/v1/api-keys/{id}`). Breaking changes only in `/api/v2`.
- Every list uses cursor pagination (`limit`, `cursor`, `next_cursor`, `has_more`).
- Every endpoint has auth, a rate limit and the problem+json error format. A request ID travels through every service and appears in logs and errors.
- Telemetry ingest uses the standard OTLP paths (`/v1/logs`, `/v1/traces`, `/v1/metrics`).

## Data and security rules

- Store every timestamp in UTC. Convert only for display. Exports use ISO 8601 UTC.
- Every ClickHouse and Postgres query on tenant data filters by `org_id`, and by `project_id` where it applies. No exceptions.
- Every ClickHouse query uses parameters. Never format values into SQL strings.
- Every log search is bounded by project and time range, returned newest first with a limit.
- Store keys only as a SHA-256 hash plus the last 4 characters, and show the key once at creation. Key prefixes are `sp_sk_` (LLM), `sp_ingest_` (data), `sp_browser_` and `sp_admin_`.
- Never log or return secrets or provider credentials.
- Prompt and response logging is off by default.
- Logs are kept for at most 7 days (ClickHouse TTL).
- The gateway fails open on telemetry. A tracing error never fails an LLM request.

## Tests

- Write tests in `tests/controllers`, `tests/services` and `tests/repositories` inside each app. Repository tests run against real databases in Docker.
- The log query parser and other parsing, budget or key logic need thorough tests.
- Every provider client needs a contract test (`tests/clients/contract`).
- Shared test fakes live in one `tests/fakes.py` per app; reuse them instead of redefining fakes per test file.

## Decisions

- **Log ingest path:** `App SDK ──OTLP/HTTP──► OTel Collector (batch, redact, forward) ──OTLP/HTTP──► Server /v1/logs ──► ClickHouse`.
  - Apps send only to the collector, never straight to the server.
  - The collector passes the data-key header through to the server. It receives with `include_metadata: true`, batches per key with `metadata_keys: [authorization]`, and forwards with the `headers_setter` extension. The collector never decides who's allowed.
  - The server checks the data key against Postgres, sets `org_id`/`project_id` from the key (never from the payload) and writes to ClickHouse in bounded batches. If ClickHouse is down, it returns `503` and the collector retries.
  - Apps may send OTLP/HTTP protobuf or JSON to the collector. The server accepts **protobuf only** (the collector always forwards protobuf), gzip-compressed or not. The collector caps batches at 1,000 records (`send_batch_max_size`).
  - gRPC: the collector accepts OTLP/gRPC on 4317 and OTLP/HTTP on 4318 from apps. The server stays HTTP-only; no `grpcio`.
  - Check order on `/v1/logs`: key → content type → body size (10 MB) → bounded gzip decompression (50 MB) → protobuf decode. Unauthenticated requests never reach the parser.
- **Python SDK (`sdk/python`, PyPI name `spanport`):**
  - Supports Python 3.12+ (it runs inside users' apps, so it can't require our server's 3.14).
  - Standard `src/` layout: public API in `src/spanport/__init__.py` (`init`, `shutdown`); internal modules start with `_`; constants in `_constants.py`. The controller/service/repository layering applies to the gateway and server, not to SDKs.
  - A thin wrapper over OpenTelemetry. It uses `opentelemetry-instrumentation-logging`'s `LoggingHandler`; the one in `opentelemetry-sdk` is deprecated. Tests fail on any `DeprecationWarning`.
  - Never breaks the host app: `init()` never raises, export happens in a background batch, and the SDK's own export-path loggers are never exported.
  - A separate uv project (`sdk/python/pyproject.toml` + its own `uv.lock`), excluded from the server workspace, so it can be tested on 3.12. Build backend `uv_build`.
  - Checks its data key once at start-up, in a background thread, with `GET /api/v1/api-keys/current` on the server (stdlib `urllib`). A rejected key is an error on stderr; logs still go only to the collector.
  - The SDK's own messages use the `spanport` logger: stderr only, never propagated to the root logger, never exported.
- **Node.js SDK (`sdk/node`, npm name `spanport`):**
  - Node 22.15+, ESM only (CommonJS apps can `require()` it on Node 22.12+). OpenTelemetry JS 3.0 line. TypeScript 6 (typescript-eslint doesn't support 7 yet), strict `tsc` and eslint; tests use Node's built-in `node:test`.
  - Same behaviour as the Python SDK: `init()` never throws, background OTLP/HTTP batches to the collector, start-up key check with `fetch`, trace_id/span_id from the active span, the SDK's own messages on stderr only.
  - `console.*` is captured by default (original output unchanged; `captureConsole: false` turns it off). pino and winston write JSON lines to `spanport.logStream()`, so the SDK depends on neither.
- **UI (`ui/`):** React 19 + Vite 8, TypeScript 6 strict, ESLint with typescript-eslint strictTypeChecked and react-hooks; tests with Vitest + Testing Library (jsdom), next to the code as `*.test.ts(x)`.
  - Signed-in state comes from `GET /api/v1/auth/me` (TanStack Query); any 401 sets it to null, which shows Sign in. Signing in or out clears the query cache. The UI never holds a key or session token: the session cookie is HttpOnly, and POSTs send the `__Host-sp_csrf` cookie's value as `X-CSRF-Token`.
  - The UI follows the design canvas (claude.ai artifact "Spanport: UI"); parts that need later steps are shown disabled with "Coming in a later release".
  - The browser talks to one origin: nginx (Docker) or Vite's proxy (dev) forwards `/api` to the server. The image is two stages (Node build, `nginx` serve as the non-root `nginx` user); proxy buffering is off for live tail.
  - Explorer state (project, range, chips, query, live) lives in URL params; timezone (UTC default) in the Zustand store. Components may not call `fetch` or import a feature's `api.ts` (ESLint).
  - zod is imported as `import * as zod from "zod"`, never `z`.
- **Errors:** domain exceptions live in each app's `core/errors.py` (no FastAPI import, so services can raise them); one exception handler turns them into problem+json responses.
- **CLI:** admin commands live in `server/src/spanport_server/cli/`: `migrate`, `rollback-postgres`, `rollback-clickhouse`, `create-data-key`, `create-admin-key`, `list-keys`, `revoke-key`, `reset-password` (asks for the password; signs the user out everywhere). Raw keys go to stdout once, never to logs; key ids (for revoking) are in the creation log line and `list-keys`.
- **API keys:** one `api_keys` table. Data keys belong to one project. Admin keys belong to one org, carry scopes (`logs:read`, `projects:read`) and must expire within 90 days (enforced by the service and a DB check). All key checks go through one key auth service (type, revoked, expired, scope; no cache).
- **Sign-in (step 7, first part):**
  - Tables `users` (role owner/admin/member/viewer, lower-case unique email, Argon2id hash via `argon2-cffi`), `user_sessions` (SHA-256 of the session id and CSRF token, `last_seen_at`, `revoked_at`) and `setup_tokens` (hash, 1-hour expiry, single use); migration 0003.
  - While no user exists, start-up logs a one-time setup token (`setup_token=...`). The server knows nothing about the UI's address: the person opens the UI's `/setup` page and pastes the token. Setup creates the Owner and the org (or joins an existing org with that slug) in one transaction with using up the token.
  - Cookies `__Host-sp_session` (HttpOnly, Secure, SameSite=Lax) and `__Host-sp_csrf` (readable, SameSite=Strict); 8-hour idle timeout checked on every request; logout and password reset revoke sessions in Postgres. No Redis yet.
  - Login rate limit, per email: 5 wrong passwords within 15 minutes (unknown emails count too) refuse that email with 429 `rate_limited` and `Retry-After` until the oldest of them leaves the window; a successful sign-in clears the count. Table `login_failures` (SHA-256 of the email, time; old rows deleted as new ones arrive), migration 0008, methods on `UserRepository`. No per-IP limit yet: behind nginx the server can't see the browser's address reliably (port 8000 is also published, so forwarded headers could be faked).
  - Not built yet: Google sign-in, two-factor codes, per-IP limits, `SPANPORT_OWNER_EMAIL` / `SPANPORT_OWNER_PASSWORD_FILE`.
- **Users and invites (step 7):** table `invites` (org, lower-case email, role, SHA-256 of the token, `invited_by`, 7-day `expires_at`, `accepted_at`, `cancelled_at`); migration 0007. An invite grants nothing until the invited person opens `/accept-invite?token=...` (the UI builds the link from `window.location.origin`; the server never knows the UI's address and doesn't email it), sees who it is for (`POST /api/v1/invites/inspect`) and presses Accept (`POST /api/v1/invites/accept`, creates the user and signs in). A new invite for the same email cancels the earlier one; an email with an account can't be invited, except a removed user of the same org, who gets their account back.
  - `TeamService` (owners and admins via `require_manager`): list users, change role, remove (sets `users.disabled_at`, so alert history keeps names, and revokes sessions), create, list and cancel invites. Only owners grant or change the owner role, nobody changes or removes themselves, and the last active owner can't be demoted or removed (checked with the org's owners locked `FOR UPDATE`). `Caller.role` carries the actor's role.
  - UI: Setup → Users (invite form with the link to copy, people with a role picker, pending invites with Cancel) and the public Accept invite page.
- **Per-project access:** owners and admins always see every project; a member or viewer sees all projects (`users.all_projects`, the default) or only the projects in `project_members`; invites carry `all_projects` and `project_ids` and apply them on accept (migration 0009). Deleting a project or user removes its rows.
  - `UserRecord.project_ids` / `Caller.project_ids` (None = every project) are loaded with the session user; `Caller.can_see(project_id)` is checked by log search, counts and tail, the projects list (`list_projects(..., only_ids)`), alert rules, and alerts (list, acknowledge and resolve look up the alert's project). A project the caller can't see answers 404, like one that doesn't exist. Admin keys are org-wide.
  - `PUT /api/v1/users/{id}/projects` (`{all_projects, project_ids}`, owners and admins) changes a member's or viewer's projects; promoting someone to admin or owner gives them every project. Limited access needs at least one project of the org.
  - UI: Clients and projects, API keys and Users are owner/admin screens: the sidebar lists them only for managers (`NavItem.managersOnly`, `lib/roles.ts isManager`) and their routes show a short note to anyone else (`components/layout/ManagersOnly`). The server still enforces every rule.
  - UI: the invite form shows "All projects / Only these projects" with project checkboxes for members and viewers; the Users table has a Projects column and "Edit projects".
- **Projects and keys from the UI:** `POST /api/v1/projects` (client, project, environment as slugs; 409 if it exists), `GET`/`POST /api/v1/api-keys` and `POST /api/v1/api-keys/{id}/revoke` need a signed-in owner or admin (`require_manager`, 403 `insufficient_role` otherwise); admin keys can't manage keys. Keys have a `name` (migration 0004). The raw key is returned once by the create call and never listed.
  - Projects: `PATCH /api/v1/projects/{id}` (rename or change environment; 409 on a clash), `POST .../archive` and `.../restore`. Archiving sets `projects.archived_at` (migration 0005): the project's data keys stop authenticating (`find_by_hash` skips them), its logs stay. `DELETE /api/v1/projects/{id}` works only on archived projects (409 otherwise): it deletes the project's logs in ClickHouse first (so a ClickHouse outage loses nothing), then its keys and the project in one Postgres transaction; the UI asks for the project name to be typed. Keys: `PATCH /api/v1/api-keys/{id}` renames; `DELETE /api/v1/api-keys/{id}` removes only revoked keys (404 otherwise).
  - Environments are any slug; the UI offers production, staging, development, the ones already used, and "+ Environment", warning when a new one looks like an existing one (e.g. `prod` vs `production`).
- **Log alerts (step 7):** email only for now (no Slack or webhooks). Tables `alert_rules` (project, name, query in the log query language, `threshold`, `window_minutes` 1 to 60, 1 to 10 `email_recipients`, `enabled`, `next_check_at`) and `alert_events` (firing → acknowledged → resolved, `acknowledged_by` / `resolved_by` users, null `resolved_by` means it resolved itself; one open alert per rule by a partial unique index); migration 0006. Deleting a project cascades to its rules, a rule to its alerts.
  - A background loop in the server (`jobs/alert_check_job.py`, started in the lifespan) runs every minute: for each organization it claims due rules with `FOR UPDATE SKIP LOCKED` (so replicas never double-check), counts matching lines with the log search repository, opens an alert when the count is **more than** the threshold and resolves it when it isn't. One email on fire, one on self-resolve; a mail failure is logged and the alert state stays. ClickHouse down skips the rule until its next check.
  - Email is stdlib `smtplib` in a thread (`clients/email_client.py`), configured by `SPANPORT_SMTP_*`; port 465 uses SSL from the start, other ports STARTTLS. Without `SPANPORT_SMTP_HOST` rules can't be saved. Emails carry counts and the query, never log lines.
  - Each email is HTML with a plain-text part (multipart/alternative). `services/alert_email.py` builds one `AlertEmail` (firing, resolved or test) and renders it with `templates/alert_email.html` (+ `alert_email_row.html`, `string.Template`, inline styles for Gmail and Outlook) and as text; every user-typed value is HTML-escaped.
  - Optional `SPANPORT_UI_URL` (http/https only), used **only** for email links: **Open alert** (`/alerts?project=`) and **See matching logs** (`/logs?project=&range=absolute&start=&end=&query=&mode=query` over the window that fired). Without it emails have no buttons. The UI route and param names live in `core/constants.py` and must match `ui/src/constants`.
  - Owners and admins manage rules and send tests (`require_manager`); owners, admins and members acknowledge and resolve (`require_responder`); everyone signed in reads (`require_signed_in`). `Caller.user_id` records who acted; admin keys can't act on alerts.
  - UI: Setup → Alerts with "Now and history" and "Rules" tabs; the rule form has preset searches and a live preview ("would fire / would not fire" from `/api/v1/logs/counts`); Logs has **Create alert** (owners and admins), which opens a new rule with the current search. Sidebar links keep the `project` URL param.
- **Traces ingest (step 8, B1):** `App ──OTLP──► Collector (traces pipeline, same per-key batching) ──► Server /v1/traces ──► ClickHouse spans`. Same checks and limits as `/v1/logs` (shared `core/compression.decode_otlp_body`); org and project from the data key. Table `spans` (ClickHouse migration 0002): ids, parent, service, name, kind, category, start/end, `duration_ns`, status, `http_method`/`http_route`/`http_status` (current and older OTel attribute names), attributes; ORDER BY `(org_id, project_id, service, category, start_ts)`, 30-day TTL (spans older than that are dropped at ingest). Category at ingest, first match wins: `llm` (`gen_ai.*`) → `db` (`db.system`) → `client` (CLIENT/PRODUCER) → `incoming_request` (SERVER/CONSUMER) → `code`; "service call" vs "external HTTP" for a client span is decided when a trace is read. Deleting a project deletes its logs and spans (`ProjectDataRepository`). Not built yet: SDK tracing (B2), API monitoring (B4).
- **Requests screen (step 8, B3):** `POST /api/v1/traces/search` (project, range within 30 days, optional service, route contains, `min_duration_ms`, `errors_only`; incoming-request spans newest first, cursor on `(start_ts, span_id)`) and `GET /api/v1/traces/{trace_id}?project_id=` (the trace's spans in that project, at most 2,000, `truncated` beyond). Same callers as log search (`logs:read` admin key or any signed-in role); projects the caller can't see are 404. `services/trace_shape.py` builds the waterfall: offsets, own time (duration minus the union of child intervals) and labels (a client span is `service_call` when a server span or another service joined under it, else `external`). UI: Monitor → Requests (`/requests`, filters in the URL) and `/requests/:traceId` (nested waterfall, own time, click a step for its attributes, **See logs** opens Logs with `trace:<id>` a minute either side).
- **Log export (step 7):** `POST /api/v1/logs/export` = the search body + `format` (`csv` | `ndjson`). The service checks role (viewers 403), uses the same `bounded_query` as search (org, visible projects, 7 days), counts first and refuses more than 100,000 lines (400, "narrow the range"), then streams newest first in keyset batches of 5,000 with `Content-Disposition` `spanport-logs-<client>-<project>-<env>-<YYYYMMDD-HHMM>.<ext>`. CSV columns ts, level, service, message, trace_id, span_id, client_ip, user_id; cells starting with `= + - @` get a leading `'` (formula injection). NDJSON has every field. Background exports by email stay deferred. UI: the Export menu's Download CSV / JSON lines (fetch → blob → save in `useLogExport`), disabled with a reason for viewers and over the limit.
- **Log search:** `/api/v1/logs/search`, `/api/v1/logs/counts`, `/api/v1/logs/tail` (`logs:read`) and `GET /api/v1/projects` (`projects:read`) accept an admin key in `Authorization` (scripts) or, without that header, a signed-in session (any role; CSRF header on POST). Services receive a `Caller` (org id plus a log label), never a key or user.
  - Live tail is server-sent events over `POST` (the UI reads it with `fetch`, since `EventSource` can't send headers). Every 2 s it re-reads the last 30 s and skips `log_id`s already sent; a heartbeat comment every 15 s keeps proxies from closing it.
  - The key is checked before the body is read; the body is capped at 64 KB and validated with errors that name fields, never echo values.
  - The project must belong to the key's org (404 otherwise). The range must start within 7 days.
  - Chips and text query → condition tree. With `combine: "and"` (the UI always sends it), chips on the same field and operator are alternatives (`=`/`:` → OR, `!=`/`!:` → all must hold) and different fields must all match. The UI's level cards are the level filter (they add `level = X` chips, which the chip area hides) and their counts leave the level chips out, so a hidden level still shows its count. The parser is a service; the SQL compiler is a repository, because services never write SQL. Columns come from an allowlist; every value and attribute key is a bound parameter.
  - Paging is exact: each log row has a UUIDv7 `log_id` set at ingest; pages continue after `(ts, log_id)` via an opaque cursor.
  - Admin keys: `project_id` is NULL, `scopes` and `expires_at` set; DB checks tie these to the key type (migration 0002). A valid key without the scope gets 403 `insufficient_scope`, every other key failure 401.
  - Validation errors list field names and reasons only (`errors(include_input=False)`); search log lines record counts and flags, never the query text.

## License

Apache 2.0 (see [LICENSE](LICENSE)).

## Repository

https://github.com/span-port/spanport (org `span-port`; `Spanport` on GitHub belongs to someone else).
