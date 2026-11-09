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
- Every endpoint has auth, a rate limit and the problem+json error format. Rate limits are in-process token buckets (`core/rate_limiter.py`, moves to `packages/core` with the gateway): per user or admin key on `/api/v1` (`SPANPORT_RATE_LIMIT_PER_MINUTE`, lower `_EXPENSIVE_PER_MINUTE` for searches, exports, APIs, errors, map and traces), per client address on setup, login and invites (`_PUBLIC_PER_MINUTE`; `X-Real-IP` trusted only from a private-network peer); 429 `rate_limited` with `Retry-After`. `/health` and OTLP ingest are not limited. Counts are per process. A request ID travels through every service and appears in logs and errors.
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
  - Check order on `/v1/logs`: key → content type → body size (10 MB) → bounded gzip decompression (10 MB) → record count read from the raw bytes (at most 5,000 records or spans, 413 otherwise) → protobuf decode in a worker thread. Unauthenticated requests never reach the parser; a malformed key is refused without a Postgres lookup. Out-of-range values (times, severity, status, duration, long names and paths) are clamped or cut; a value ClickHouse still refuses is a 400. Inserts go in chunks of 1,000 rows.
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
  - Login rate limit, per email: 5 wrong passwords within 15 minutes (`SPANPORT_LOGIN_FAILURE_LIMIT` / `_WINDOW_MINUTES`; unknown emails count too) refuse that email with 429 `rate_limited` and `Retry-After` until the oldest of them leaves the window; a successful sign-in clears the count. Table `login_failures` (SHA-256 of the email, time; old rows deleted as new ones arrive), migration 0008, methods on `UserRepository`. No per-IP limit yet: behind nginx the server can't see the browser's address reliably (port 8000 is also published, so forwarded headers could be faked).
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
- **Log alerts (step 7):** email only for now (no Slack or webhooks). Tables `alert_rules` (project, name, query in the log query language, `threshold`, `window_minutes`, `email_recipients`, `enabled`, `next_check_at`) and `alert_events` (firing → acknowledged → resolved, `acknowledged_by` / `resolved_by` users, null `resolved_by` only on alerts that closed themselves before migration 0010; one open alert per rule by a partial unique index); migration 0006. Deleting a project cascades to its rules, a rule to its alerts.
  - A background loop in the server (`jobs/alert_check_job.py`, started in the lifespan) runs every `SPANPORT_ALERT_CHECK_SECONDS` (default 10, 5 to 300): for each organization it claims due rules with `FOR UPDATE SKIP LOCKED` (so replicas never double-check), counts matching lines with the log search repository, opens an alert when the count is **more than** the threshold and marks it back to normal (`recovered_at`) when it isn't; an alert never closes itself, a person resolves it (migration 0010: `assigned_to`, `recovered_at`, `resolution_note`), and breaking the rule again while it's open clears `recovered_at` and emails Firing again. Each check counts 15 s before the window too (`ALERT_CHECK_OVERLAP`, so lines that reach storage late are never missed), and a checked rule is due again 2 s before the next round (`ALERT_CHECK_EARLY`, so a round that wakes early doesn't skip it). Limits are settings too, checked by `AlertRuleService`: `SPANPORT_ALERT_MAX_EMAILS` (10), `_MAX_WINDOW_MINUTES` (60), `_MAX_RULES_PER_PROJECT` (50); the request schema only caps them at the settings' ceilings. `GET /api/v1/alert-settings` (anyone signed in) gives the UI the interval and limits, so the Alerts page refreshes at the check interval and the form uses the server's limits. One email on fire, one on back to normal (says it stays open), one to the person it's assigned to (not when assigning yourself); a mail failure is logged and the alert state stays. ClickHouse down skips the rule until its next check.
  - Email is stdlib `smtplib` in a thread (`clients/email_client.py`), configured by `SPANPORT_SMTP_*`; port 465 uses SSL from the start, other ports STARTTLS. Without `SPANPORT_SMTP_HOST` rules can't be saved. Emails carry counts and the query, never log lines.
  - Each email is HTML with a plain-text part (multipart/alternative). `services/alert_email.py` builds one `AlertEmail` (firing, resolved or test) and renders it with `templates/alert_email.html` (+ `alert_email_row.html`, `string.Template`, inline styles for Gmail and Outlook) and as text; every user-typed value is HTML-escaped.
  - Optional `SPANPORT_UI_URL` (http/https only), used **only** for email links: **Open alert** (`/alerts?project=`) and **See matching logs** (`/logs?project=&range=absolute&start=&end=&query=&mode=query` over the window that fired). Without it emails have no buttons. The UI route and param names live in `core/constants.py` and must match `ui/src/constants`.
  - Owners and admins manage rules and send tests (`require_manager`); owners, admins and members acknowledge ("I'm on it" also assigns yourself), assign (`POST /api/v1/alert-events/{id}/assign` `{user_id}`: an active owner, admin or member of the org who can see the project; `GET /api/v1/alert-assignees?project_id=` lists them) and resolve (`{note}`, up to 2,000 characters, shown in History) (`require_responder`); everyone signed in reads (`require_signed_in`). `Caller.user_id` records who acted; admin keys can't act on alerts.
  - UI: Setup → Alerts with "Now and history" and "Rules" tabs; the rule form has preset searches and a live preview ("would fire / would not fire" from `/api/v1/logs/counts`); Logs has **Create alert** (owners and admins), which opens a new rule with the current search. Sidebar links keep the `project` URL param.
- **Traces ingest (step 8, B1):** `App ──OTLP──► Collector (traces pipeline, same per-key batching) ──► Server /v1/traces ──► ClickHouse spans`. Same checks and limits as `/v1/logs` (shared `core/compression.decode_otlp_body`); org and project from the data key. Table `spans` (ClickHouse migration 0002): ids, parent, service, name, kind, category, start/end, `duration_ns`, status, `http_method`/`http_route`/`http_status` (current and older OTel attribute names; without `http.route`, e.g. no framework instrumentation, the route is `url.path`/`http.target` with id-like segments (numbers, UUIDs, 16+ hex, 20+ char tokens with a digit) replaced by `:id`), attributes; ORDER BY `(org_id, project_id, service, category, start_ts)`, 30-day TTL (spans older than that are dropped at ingest). Category at ingest, first match wins: `llm` (`gen_ai.*`) → `db` (`db.system.name` or the older `db.system`) → `client` (CLIENT/PRODUCER) → `incoming_request` (SERVER/CONSUMER) → `code`; "service call" vs "external HTTP" for a client span is decided when a trace is read. Deleting a project deletes its logs and spans (`ProjectDataRepository`).
- **SDK tracing (step 8, B2; released in SDKs 1.0.0, git tags `sdk-node-v1.0.0` and `sdk-python-v1.0.0`; 0.2.0 was never published; Node 1.0.1 bundles the Express, pg and undici instrumentations):** both SDKs send traces by default (`traces: false` / `traces=False` turns them off) to the collector's `/v1/traces` with the data key, batched in the background, and never trace their own sends.
  - Node: runtime deps `@opentelemetry/sdk-trace`, `context-async-hooks`, `core` (W3C `traceparent` propagation), `exporter-trace-otlp-http`, `instrumentation`, `instrumentation-http`, and since 1.0.1 `instrumentation-express` (0.72), `instrumentation-pg` (0.77) and `instrumentation-undici` (0.34) (ranges up to the next 0.x minor, vetted floors). All are always registered, so apps install nothing extra; each patches only a library the app actually loads, and fetch calls to the SDK's own hosts are ignored like http ones. The HTTP instrumentation is created once per process and never switched off (built-ins can't be re-patched), and `node:http`/`node:https` are required once so ESM apps are timed too. `spanport.trace()` class decorator ("Class.method", copies reflect-metadata so NestJS routes survive) and `spanport.withSpan(name, fn)`. `init()` should run from a file imported before the framework.
  - Python: no new runtime deps; library instrumentations are extras (`spanport[fastapi|flask|django|sqlalchemy|psycopg|httpx|requests|all]`) switched on if installed, each given the SDK's own `TracerProvider` (the global one is never set, so `init()` after `shutdown()` works and an app's own OTel setup is untouched). `@spanport.trace()` for functions or classes (sync and async) and `with spanport.span(name)`. `init()` should run before the web app is created.
- **Requests screen (step 8, B3):** `POST /api/v1/traces/search` (project, range within 30 days, optional service, route contains, `min_duration_ms`, `errors_only`; incoming-request spans newest first, cursor on `(start_ts, span_id)`) and `GET /api/v1/traces/{trace_id}?project_id=` (the trace's spans in that project, at most 2,000, `truncated` beyond). Same callers as log search (`logs:read` admin key or any signed-in role); projects the caller can't see are 404. `services/trace_shape.py` builds the waterfall: offsets, own time (duration minus the union of child intervals) and labels (a client span is `service_call` when a server span or another service joined under it, else `external`). UI: Monitor → Requests (`/requests`, filters in the URL) and `/requests/:traceId` (cards splitting the time into your code / database / external calls / LLM from each step's own time, a waterfall on one time axis whose bars grow in one after another (off with reduced motion), collapsible steps, the chosen step's details in a side panel, **See logs** opens Logs with `trace:<id>` a minute either side).
- **API monitoring (step 8, B4):** `POST /api/v1/endpoints/summary` (project, range within 30 days, optional service; same callers as Requests) returns totals (requests, errors, p95) and the 200 busiest endpoints (`has_more` beyond; an aggregate, so no cursor). An endpoint is (service, method, `http_route` or else the span name). `repositories/clickhouse/endpoint_repository.py` sums, per endpoint, count, errors, `quantiles(0.5, 0.95, 0.99)` and the database / client / LLM step time of the same trace and service (a step inside another such step isn't counted twice; steps are looked for up to 1 hour past the range). `services/endpoint_service.py` turns that into average ms per request per kind of step; "your code" is the rest, and parallel steps that add up to more than the request are scaled to fit. Range and visibility checks are shared with `TraceService` (`span_range`, `check_visible_project`). The summary also returns each endpoint's and the totals' `previous_p95_ms` (the period of the same length just before) and `slow_queries`: the 10 database queries with the most total time per endpoint (text from `db.query.text`, else `db.statement`, else the span name, cut to 500 characters; calls per request).
  - UI: Monitor → APIs (`/apis`) follows the canvas: tabs (Overview; Deploys and Service map coming later), the project and range in the description, the shared time range picker (quick ranges up to 30 days, Custom, timezone: `TimeRangePicker` / `CustomRangeDialog` in `components/ui` with `RangeRules`, Logs and APIs passing their own), cards (p95 with the change vs the period before; LLM spend coming later), "What do p50, p95 and p99 mean?" with the busiest API's numbers and "N slower" under each percentile, the slowest API's latency chart, the "All APIs" table (red line when p95 is at least 2× the period before; Cost per request coming later) whose rows open the API detail page, and Slow queries ("N+1 pattern" from 5 calls per request).
  - API detail: `POST /api/v1/endpoints/detail` (the summary body + `service`, `http_method`, `route`; same callers) returns the endpoint's summary (null without requests), a timeline (requests, failures, p95 per interval of about 1/60 of the range, whole minutes), status codes, its steps (every non-request span in the same trace and service, grouped by category and name: calls, calls per request, avg, p95, total; 25 most total time) and its 10 slowest requests. `repositories/clickhouse/endpoint_detail_repository.py` reuses the list's request selection narrowed by `ENDPOINT_SQL`; `services/endpoint_detail_service.py`. UI: `/apis/detail?project=&service=&method=&route=&range=` with cards, an SVG chart (requests bars, failures in red, p95 line), where time goes in ms, status codes, the steps table and the slowest requests (each opens its waterfall); **See requests** opens Requests filtered. Not built yet (later steps): latency over time, LLM cost per request, deploys, slow-query hints.
- **Service map (APIs → Service map):** `POST /api/v1/service-map` (project, range within 30 days; same callers as APIs) returns boxes (`service` for your services, `db`, `external`, `llm`; id `<kind>:<name>`) and lines with calls, errors, p50 and p95, and `range_seconds` for rates. `repositories/clickhouse/service_map_repository.py` reads three things per period: each service's incoming requests (the APIs list's selection), its database / outgoing / LLM calls by target (database: `db.system.name` or `db.system`, else "database", plus ` · ` and `db.namespace` or `db.name`; outgoing: `server.address`, `net.peer.name`, `http.host`, else the host of `url.full` / `http.url`, else the span name; LLM: `gen_ai.provider.name` or `gen_ai.system`, else the span name; a call inside another such call and an outgoing call one of your services answered are left out; a `client` span with a database system attribute counts as a database call, since spans stored before ingest knew `db.system.name` were filed as outgoing calls), and service-to-service requests (an incoming span whose parent is another service's span, parents looked for from 5 minutes before the range); 200 lines of each kind at most. `services/service_map_service.py` adds up a non-service box from its lines (typical time weighted by calls, p95 the slowest line's) and colours boxes and lines: red above 1% failed, orange at 2× the p95 of the period of the same length just before. UI: `/apis/map` (the APIs tabs are links now, keeping project and range; Deploys disabled): boxes in columns, callers left of what they call (`lib/serviceMap.ts`), SVG curves labelled "rate · p50" (or the error share when red), and a details panel for the chosen box (the busiest service at first) with a link to APIs, Errors or Requests. Boxes show a logo beside the name: a brand logo from `simple-icons` (16.36.0, CC0, no dependencies; only the imported icons are bundled) when the name contains one of the keywords in `constants/mapLogos.ts` (first match wins; brand colours too dark for the boxes use the text colour), else a drawn icon for the kind (server, database, globe, sparkle). AWS, OpenAI, Azure, Slack and Twilio aren't in simple-icons, so they get the drawn icon. Not built yet: the browser app box (web SDK), cache hit rate, LLM cost.
- **HTTP errors (Monitor → Errors):** `POST /api/v1/errors/summary` (project, range within 30 days, optional API as `service` + `http_method` + `route`; `route` needs `service`; same callers as APIs) returns 4xx and 5xx per interval (`bucket_seconds` as on the API detail page, empty intervals left out), totals with the interval with the most 5xx, and the failing APIs (always over every API, for the API filter). `POST /api/v1/errors/window` (the same body for one bar's start and end + `show`: `all` | `5xx` | `4xx`) returns the count, failures by status and API (50 most), and the 20 newest failing requests with the caller's address (`client.address`, else `http.client_ip`, else `net.peer.ip`) and "what the code logged" (the trace's most severe log line in the project, cut to 300 characters). Statuses come from `http_status` of incoming-request spans. `repositories/clickhouse/error_repository.py` reuses the APIs list's request selection; `services/error_service.py`. UI: `/errors?project=&range=&show=&service=&method=&route=` following the canvas: tabs (HTTP errors; Grouped coming later), Show and API filters, cards (5xx with its share, 4xx, worst moment for 5xx, requests), stacked bars (each a button), and the chosen bar's panel with links to Requests (failed requests over the shortest quick range reaching the bar, since Requests has quick ranges only), Logs (`level:ERROR` over the bar) and Grouped (coming later), a by-status table and the newest requests (each opens its waterfall). Not built yet: grouped errors (needs span exception events stored), deploy markers.
- **Storage (Setup -> Data -> Storage):** `GET /api/v1/storage` (owners and admins) lists every project of the org with its log lines and request steps (rows, oldest, newest per ClickHouse table, scoped by `org_id`), an estimated size (rows times the table's average bytes per row from `system.parts`, the only table-wide figure, so other orgs' data is never exposed), totals and retention (7 / 30 days). `redis_in_use` stays false until the gateway adds Redis. UI: `/data` with the Storage tab (Integrations and Settings shown as coming later). Not built: deleting data from here (deleting an archived project already removes its data).
- **Log export (step 7):** `POST /api/v1/logs/export` = the search body + `format` (`csv` | `ndjson`). The service checks role (viewers 403), uses the same `bounded_query` as search (org, visible projects, 7 days), counts first and refuses more than 100,000 lines (400, "narrow the range"), then streams newest first in keyset batches of 5,000 with `Content-Disposition` `spanport-logs-<client>-<project>-<env>-<YYYYMMDD-HHMM>.<ext>`. CSV columns ts, level, service, message, trace_id, span_id, client_ip, user_id; cells starting with `= + - @` get a leading `'` (formula injection). NDJSON has every field. Background exports by email stay deferred. UI: the Export menu's Download CSV / JSON lines (fetch → blob → save in `useLogExport`), disabled with a reason for viewers and over the limit.
- **Log search:** `/api/v1/logs/search`, `/api/v1/logs/counts`, `/api/v1/logs/tail` (`logs:read`) and `GET /api/v1/projects` (`projects:read`) accept an admin key in `Authorization` (scripts) or, without that header, a signed-in session (any role; CSRF header on POST). Services receive a `Caller` (org id plus a log label), never a key or user.
  - Live tail is server-sent events over `POST` (the UI reads it with `fetch`, since `EventSource` can't send headers). Every 2 s it re-reads the last 30 s and skips `log_id`s already sent; a heartbeat comment every 15 s keeps proxies from closing it.
  - The key is checked before the body is read; the body is capped at 64 KB and validated with errors that name fields, never echo values.
  - The project must belong to the key's org (404 otherwise). The range must start within 7 days.
  - Chips and text query → condition tree. With `combine: "and"` (the UI always sends it), chips on the same field and operator are alternatives (`=`/`:` → OR, `!=`/`!:` → all must hold) and different fields must all match. The UI's level cards are the level filter (they add `level = X` chips, which the chip area hides) and their counts leave the level chips out, so a hidden level still shows its count. The parser is a service; the SQL compiler is a repository, because services never write SQL. Columns come from an allowlist; every value and attribute key is a bound parameter.
  - Paging is exact: each log row has a UUIDv7 `log_id` set at ingest; pages continue after `(ts, log_id)` via an opaque cursor.
  - Admin keys: `project_id` is NULL, `scopes` and `expires_at` set; DB checks tie these to the key type (migration 0002). A valid key without the scope gets 403 `insufficient_scope`, every other key failure 401.
  - Validation errors list field names and reasons only (`errors(include_input=False)`); search log lines record counts and flags, never the query text.
- **Security hardening (after the review of 2026-11-09):**
  - Server port 8000 is published on `127.0.0.1` only; apps reach `/api` through the UI's nginx. Start-up refuses the `change-me` database passwords. FastAPI docs are off unless `SPANPORT_API_DOCS=true`.
  - ClickHouse reads are capped by `SPANPORT_CLICKHOUSE_MAX_EXECUTION_SECONDS` (30) and `_MAX_MEMORY_BYTES` (2 GiB); hitting one is 400 `query_too_expensive`.
  - Collector: `memory_limiter` first, 10 MiB per request, `metadata_cardinality_limit` 200, and a `routing` connector that drops requests without `Bearer sp_ingest_`. Optional TLS: `collector/config.tls.yaml` as a second `--config` with a mounted certificate.
  - Argon2 runs in a 4-thread pool, never on the event loop; setup and invite tokens are checked before hashing. Login attempts are serialized per email with an advisory lock and recorded before the password check; `reset-password` clears the lock. Sessions also end `SPANPORT_SESSION_MAX_HOURS` (168) after sign-in. Setup runs one at a time and a new setup token ends older ones. A role that changed meanwhile answers 409.
  - Removing or demoting an owner or admin cancels the invites they sent and revokes the admin keys they created (`api_keys.created_by`, migration 0011). An email with an account in another org gets the generic 409 "This email can't be invited." Assignee emails are shown to owners and admins only.
  - Live tail re-checks the caller every 60 s, ends after `SPANPORT_TAIL_MAX_MINUTES` (60) and allows `SPANPORT_RATE_LIMIT_CONCURRENT_TAILS` (3) per caller (the UI reconnects, also after 429). One export at a time per caller (`_CONCURRENT_EXPORTS`). Ranges may end at most 1 hour from now; cursors are at most 256 characters and their time must be inside the range. CSV export also guards cells starting with `|` or a newline, after leading spaces.
  - Alert email: the SMTP certificate is verified, each recipient gets their own message, addresses reject `, ; < > ( ) [ ] " \` and whitespace, rule names and queries reject control characters, and a failing rule is logged and skipped without stopping the round. Send test: once a minute per rule and `SPANPORT_RATE_LIMIT_ALERT_TESTS_PER_DAY` (20) per person; at most `SPANPORT_ALERT_MAX_EMAILS_PER_HOUR` (100) alert emails per org. Assigning emails only when the assignee changes.
  - UI: nginx sends CSP (no `unsafe-inline`), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer` and `server_tokens off`, and passes `X-Real-IP`. Invite links are `/accept-invite#token=...` (old `?token=` links still work) so tokens stay out of server logs. Sign in, Setup and Accept invite say "Spanport needs HTTPS" over plain http to a non-local host.
  - SDKs (Python 1.0.1, Node 1.0.2, not yet published): without `server_url`/`serverUrl` the start-up key check runs only when the collector is local, otherwise it is skipped with a note to set it to the UI's URL; a warning when a key would cross plain http to another host; Node `logStream` caps an unfinished line at 1 MB and catches its own errors.

## License

Apache 2.0 (see [LICENSE](LICENSE)).

## Repository

https://github.com/span-port/spanport (org `span-port`; `Spanport` on GitHub belongs to someone else).
