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

The build order is **logs first, then LLM**, which differs from the PRD's order. No step is done yet.

1. Foundation: monorepo skeleton, Docker Compose (Postgres, ClickHouse, OTel Collector, server), server skeleton with `/health`
2. Log ingest: orgs, clients, projects and data keys in Postgres; the ClickHouse `logs` table; `POST /v1/logs`; a CLI command to create a data key
3. Python SDK: `spanport.init(data_key=..., service=...)`, a `logging` hook, trace_id/span_id on each log; collector gRPC receiver
4. Logs query API: filter chips and the text query compiled to parameterized ClickHouse SQL; admin keys
5. UI logs explorer: project switcher, time picker (UTC default), filter bar, live tail
6. Auth (setup link, login, roles), export, log alerts, Node.js SDK
7. Then the LLM work in the PRD's order: gateway core, streaming and cost, tracing and API monitoring, security, LLM debugging and Claude Code analytics

Build only the current step. Don't scaffold for later steps.

## Scope rules

- **No Terraform.** Deployment is Docker Compose and Helm only.
- **No Kafka for now.** The collector batches; the server inserts each request with ClickHouse async inserts (`async_insert=1, wait_for_async_insert=1`) and replies only after the data is on disk. It returns `503` when ClickHouse is down, so the collector retries. No server-side buffer. Add the optional Kafka profile only when load tests show it's needed. Kafka integrations (forwarding and pulling) come later with the other integrations.
- Deferred until logs work end to end: integrations (CloudWatch, Loki, ELK, S3, Kafka), background exports over 100k lines, SSO, and search in place.

## Stack

| Part | Choice |
| --- | --- |
| Gateway, server, Python SDK | Python 3.14, FastAPI, Pydantic, httpx |
| Python packaging | uv 0.13.1 (`pyproject.toml` + `uv.lock`). No pip or requirements files. Run tools with `uv run …` |
| Docker | One `docker-compose.yml` at the repo root runs the whole stack; `docker-compose.dev.yml` adds hot reload and database ports. Images are built from the repo root (so `packages/core` is included), use `python:3.14.8-slim`, run as a non-root user, have health checks and keep uv out of the final image |
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

SQLAlchemy models live in `packages/core/src/spanport_core/models/`, separate from schemas.

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
- **Errors:** domain exceptions live in each app's `core/errors.py` (no FastAPI import, so services can raise them); one exception handler turns them into problem+json responses.
- **CLI:** admin commands live in `server/src/spanport_server/cli/`. Raw keys go to stdout once, never to logs.
- **API keys:** one `api_keys` table. Data keys belong to one project. Admin keys belong to one org, carry scopes (`logs:read`) and must expire within 90 days (enforced by the service and a DB check). All key checks go through one key auth service (type, revoked, expired, scope; no cache).
- **Log search:** `/api/v1/logs/search` and `/api/v1/logs/counts` need an admin key with `logs:read` until UI login exists (step 6).
  - The key is checked before the body is read; the body is capped at 64 KB and validated with errors that name fields, never echo values.
  - The project must belong to the key's org (404 otherwise). The range must start within 7 days.
  - Chips and text query → condition tree. The parser is a service; the SQL compiler is a repository, because services never write SQL. Columns come from an allowlist; every value and attribute key is a bound parameter.
  - Paging is exact: each log row has a UUIDv7 `log_id` set at ingest; pages continue after `(ts, log_id)` via an opaque cursor.

## License

Apache 2.0 (see [LICENSE](LICENSE)).

## Repository

https://github.com/span-port/spanport (org `span-port`; `Spanport` on GitHub belongs to someone else).
