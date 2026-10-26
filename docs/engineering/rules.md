# Spanport engineering rules

These rules apply to every pull request. CI enforces the ones marked **(CI)**. Reviewers check the rest.

## 1. Clean folder structure

```
spanport/
├── packages/core/            shared Python code (pagination, rate limits, cache, URL guard, models)
├── gateway/src/spanport_gateway/
│   ├── controllers/  services/  repositories/  clients/  schemas/  core/
├── server/src/spanport_server/
│   ├── controllers/  services/  repositories/{postgres,clickhouse,redis}/  clients/  jobs/  schemas/  core/
├── ui/src/
│   ├── app/                  router, providers, app shell, error boundary
│   ├── features/<feature>/   one folder per screen area (keys, logs, traces, costs, …)
│   │   ├── components/       display components used only by this feature
│   │   ├── hooks/            logic and data for this feature
│   │   ├── api.ts            calls for this feature
│   │   └── index.ts          what the feature exposes
│   ├── components/ui/        shared design-system components
│   ├── lib/                  pure helpers (formatting, time zones, calculations)
│   ├── api/                  HTTP client, error types
│   ├── state/                small global store (project, timezone)
│   └── config/               runtime config loader
├── sdk/{python,node,browser}/
├── db/  collector/  deploy/  docs/  tests/
```

- One feature = one folder. A file used by two features moves to `components/ui`, `lib` or `packages/core`.
- No file over about 300 lines, and no function over about 50 lines, without a reason in review.

## 2. Business logic separate from UI

- **Backend:** controllers handle HTTP only (parse, call a service, return). Services hold the rules. Repositories hold queries. Clients talk to outside systems. Calls only go downward. **(CI: import-linter)**
- **Frontend:** components only display props and raise events. Data loading, calculations and rules live in hooks (`features/*/hooks`) and pure functions (`lib`). Components never call `fetch` directly. **(CI: ESLint restricted imports)**
- Calculations (percentiles, budget %, cost, time-zone conversion) are pure functions with unit tests.

## 3. No duplicate or dead code

- Unused code, imports, exports, files and dependencies fail the build. **(CI: ruff, vulture, ESLint, knip)**
- Copy-paste above a small threshold fails the build. **(CI: jscpd)**
- No commented-out code. Git keeps history.
- Feature flags are removed once a feature is fully released.
- Before writing a helper, search `packages/core`, `ui/src/lib` and `components/ui`.
- Prefer built-ins to libraries for standard tasks: `Map.groupBy` / `Object.groupBy` for grouping, `structuredClone` for deep copies, `Intl` for number, currency and date formatting. No lodash.

## 4. Consistent naming

| Thing | Convention | Example |
| --- | --- | --- |
| Python modules, functions, variables | snake_case | `model_sync_service.py`, `get_or_load()` |
| Python classes | PascalCase | `ModelSyncService` |
| Layer files | `<name>_controller.py`, `_service.py`, `_repository.py`, `_client.py` | `key_repository.py` |
| React components and their files | PascalCase | `KeyTable.tsx` |
| Hooks | `use` + PascalCase | `useLogsSearch.ts` |
| Other TS files | camelCase | `formatCost.ts` |
| Constants and env vars | UPPER_SNAKE; env vars start with `SPANPORT_` (except standard ones like `DATABASE_URL`) | `SPANPORT_LOG_LEVEL` |
| API paths | `/api/v1/` + plural, kebab-case nouns | `/api/v1/api-keys/{id}` |
| JSON fields | snake_case | `next_cursor`, `retry_after_s` |
| Database tables and columns | snake_case, plural tables | `alert_events.started_at` |
| Redis keys | `sp:<area>:<…>` | `sp:c:key:<hash>` |
| Commits and PR titles | Conventional Commits | `feat(gateway): stop stream on disconnect` |

Words are spelled out (`project_id`, not `pid`), and the same idea gets the same word everywhere ("key", not "token", for Spanport keys).

## 5. Proper error handling everywhere

- **API errors** use one format: RFC 9457 problem details (`application/problem+json`) with `type`, `title`, `status`, `detail`, a stable `code` (e.g. `rate_limited`, `invalid_cursor`) and `request_id`.
- Services raise **domain exceptions**. One exception handler maps them to HTTP. No HTTP details inside services.
- Stack traces and internal messages are never returned to users. They are logged with the `request_id`.
- **Never swallow errors.** Every `except` either handles the error, re-raises with context, or logs it and reports a metric.
- Outside calls (providers, Redis, ClickHouse, webhooks) always have timeouts and decide clearly between fail-open and fail-closed (see Reliability decisions).
- **UI:** one typed `ApiError`; an error boundary per screen; every screen designs loading, empty, error and partial-outage states; 429 waits for `Retry-After`; messages say what happened and what to do next.
- Background jobs retry with backoff, then go to the failed list. Nothing fails silently.
- **Logs are NDJSON:** one JSON object per line to stdout, UTF-8, no pretty-printing, standard fields `ts` (ISO 8601 UTC), `level`, `message`, `service`, `trace_id`, `span_id`, then extra fields. Exports are `.ndjson.gz` (content type `application/x-ndjson`). Plain JSON is only for API responses.

## 6. Environment configuration separate from code

- All settings come from environment variables, read once at start-up into a typed, validated settings object (pydantic-settings). Missing or invalid settings stop start-up with a clear message.
- Only `.env.example` is committed, never `.env`. **(CI: secret scanning)**
- Secrets come from the secrets manager (KMS, Secrets Manager) or Docker/Kubernetes secrets, never from code or images.
- No hard-coded URLs, hostnames, ports, limits or credentials in code.
- The browser bundle contains no secrets. Runtime settings it needs (domain, feature flags) are served by the server at `/api/v1/config`.
- Environment differences live in `.env` files and Helm values, not in `if production:` branches.

## 7. Modular, reusable components

- **Shared UI components** in `ui/src/components/ui`: Button, Card, Table, Tabs, FilterChips, TimeRangePicker, ProjectSwitcher, StatusPill, CodeBlock, ConfirmPanel, EmptyState, ErrorState, Banner. Screens use these; they don't restyle their own copies.
- Components get data through typed props. Shared components contain no feature rules and make no API calls.
- **Shared backend code** lives in `packages/core`: pagination, rate limits, cache, URL guard, errors, settings base, time helpers.
- Design tokens (colors, spacing, type) are defined once as CSS variables.
- **Design tokens only:** font sizes `--text-xs` 12, `--text-sm` 13, `--text-md` 14, `--text-lg` 18, `--text-xl` 22, `--text-2xl` 28; spacing `--space-1` to `--space-8` = 4, 8, 12, 16, 24, 32, 48, 64 px; main and side panels split 1.618 to 1. No other font sizes, paddings, margins or gaps (CI: stylelint rule that rejects raw px values for these properties).
- **Visual design rules** (full table in the PRD, "Visual design rules"): dark graphite theme with one teal accent; never white or near-white surfaces, never purple; buttons, inputs and tags with 4 to 8 px corners, never pill-shaped; labels say exactly what happens (verb plus object) and numbers carry units and a comparison with normal; no emoji; no em dashes anywhere (UI text, docs, commit messages); no scroll animations, parallax or decorative motion, and none at all under reduced motion.

## 8. Proper state management

| State | Where it lives |
| --- | --- |
| Data from the server | TanStack Query (cache, refetch, retries); never copied into another store |
| Filters, time range, selected project, tab | The URL (search params), so views can be shared and survive reload |
| Small app-wide settings (timezone, theme) | One small Zustand store in `ui/src/state` |
| Forms | React Hook Form with zod schemas shared with the API types |
| Live streams | Hooks with `useRef` buffers flushed about every 250 ms (see Frontend rules) |
| Local UI (open panel, hover) | `useState` in the component |

The same piece of state never lives in two places.

## 9. Documented codebase

- Every app and package has a README: what it is, how to run it, how to test it.
- Public Python functions and classes have docstrings. Exported TypeScript functions, hooks and components have TSDoc.
- Comments explain **why**, not what.
- Decisions go in ADRs (`docs/technical/decisions/`). Product behavior goes in the PRD and BRD. Operations go in runbooks.
- The API is documented by its OpenAPI spec, generated from code, with examples on every endpoint. **(CI: spec is regenerated and checked)**
- `CHANGELOG.md` is generated from Conventional Commits on release.

## 10. Scalable API structure

- Everything under `/api/v1`. Breaking changes only in `/api/v2`, with v1 kept for 6 months.
- One router per domain (`api_keys`, `providers`, `logs`, `traces`, `storage`, …) following controller → service → repository.
- Separate Pydantic models for requests, responses and storage. Database models never leak into responses.
- Resource-style routes: `GET /api-keys`, `POST /api-keys`, `GET /api-keys/{id}`, `PATCH /api-keys/{id}`, `POST /api-keys/{id}/revoke`.
- Every list uses cursor pagination (`limit`, `cursor`, `next_cursor`, `has_more`). Filters are query parameters with consistent names.
- Every endpoint has authentication and role checks, a rate limit, and the standard error format.
- `Idempotency-Key` is supported on create operations. Long tasks return `202 Accepted` with a job ID to poll.
- A request ID travels through every service and appears in logs and errors.
- Async I/O throughout, connection pools for Postgres, Redis and ClickHouse, and no blocking calls in request handlers.
