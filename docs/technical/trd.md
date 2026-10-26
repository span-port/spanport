# Spanport: Technical Requirements Document (TRD)

| | |
| --- | --- |
| Product | Spanport: open-source, self-hosted LLM gateway and observability platform |
| Companion documents | PRD (`docs/product/prd.md`): what and why. BRD (`docs/business/brd.md`): business requirements. Database reference (`db/README.md`). Engineering rules (`docs/engineering/rules.md`) |
| Status | Design complete for v1.0; implementation follows the build order in section 15 |

This document describes **how** Spanport is built: architecture, components, data stores, interfaces, security, reliability, performance and engineering standards. Where a topic is also described in the PRD, this document is the technical source of truth.

## 1. Goals and constraints

- **Self-hosted, container-first:** every component is a container; `docker compose up` starts everything; the Helm chart runs the same images.
- **Gateway on the hot path:** the gateway adds under 15 ms at p95 to an LLM call and keeps routing calls even when ClickHouse or Redis is down.
- **No data loss for telemetry:** data is buffered (collector disk queue, optional Kafka) when storage is unavailable.
- **Multi-tenant safe:** every query is scoped to one organization, enforced in the database.
- **Free and open source:** Apache 2.0 proposed; no paid tier.

## 2. Architecture


The gateway is the only component on the request path; everything else receives telemetry asynchronously, so an observability outage never breaks an app.

```
Your apps + SDK ──LLM calls──► Gateway ──────────► LLM providers (OpenAI, Anthropic, Bedrock, Gemini)
      │                        │   ├──► Redis     (limits, budgets, cache)
      │ spans + logs           │   └──► Postgres  (keys, pricing, config)
      ▼                        │ async spans
Claude Code ──telemetry──► OTel Collector (OTLP, batching, PII redaction)
                               │
                               ▼
                           ClickHouse (spans, LLM requests, logs, rollups) ──► Web UI + alerts
```

Apps and Claude Code send spans and logs to the collector; LLM traffic passes through the gateway, which checks keys and budgets in Redis and Postgres, calls the provider, and emits a span with tokens and cost.

| Layer | Choice | Why |
| --- | --- | --- |
| Gateway | Python (FastAPI, uvicorn, httpx, Pydantic) | Async I/O handles streaming well; same language as the backend. Runs as a Docker image, so users never import it |
| SDKs | Python SDK in Python (PyPI), Node.js SDK in TypeScript (npm); both thin wrappers over OpenTelemetry | Standard, no vendor lock-in, auto-instrumentation exists |
| Ingest | OpenTelemetry Collector | One OTLP endpoint for SDKs, gateway and Claude Code |
| Buffer (large installs) | Kafka / Amazon MSK | Absorbs log spikes; no data loss during ClickHouse maintenance |
| Trace and log store | ClickHouse | Fast aggregation over very large span and log volumes |
| Config store | PostgreSQL | Keys, orgs, clients, pricing, budgets, model catalog |
| Cache and limits | Redis, two instances: redis-state and redis-cache | State never evicted; caches evicted least-recently-used |
| Scheduler | APScheduler or Kubernetes CronJob | Hourly model catalog sync, rollups |
| Secrets | AWS Secrets Manager + KMS | Provider keys never stored in plaintext |
| Frontend | React + TypeScript | Live view, dashboards, trace and log explorers, SQL box |
| UI data and lists | TanStack Query, TanStack Virtual | Caching, no race conditions, smooth long lists |
| Real-time | Server-Sent Events over HTTP/2, Redis pub/sub fan-out | One-way streams that pass any proxy and reconnect on their own |
| Deployment | Docker Compose, Kubernetes (EKS) with a Helm chart | Same images for every self-hosted install |
| Postgres access | SQLAlchemy 2.0 (async) with asyncpg; Alembic for migrations | Mature, typed, async; keeps database models separate from Pydantic schemas, matching the controller/service/repository layers |
| ClickHouse access | No ORM: clickhouse-connect with parameterized SQL inside repositories | Analytics queries (percentiles, rollups, TTL) need hand-written SQL; ORMs add little and hide performance |
| Redis access | redis-py (asyncio) | Atomic counters and Lua scripts for rate limits and budgets |

**Why the SDKs are in different languages.** The gateway and backend run as Docker images, so they can be pure Python. An SDK is imported inside the user's app, so it must be in that app's language: the npm package is TypeScript, the PyPI package is Python. Both stay small because OpenTelemetry already provides the instrumentation; apps in other languages (Go, Java, .NET) can call the gateway over HTTP and send traces and logs to the OTLP endpoint with their own OpenTelemetry SDK, no Spanport package needed.

**Repository layout (monorepo).**

```
spanport/
  gateway/      Python (FastAPI)
  server/       Python (APIs, ingest rules, model sync)
  ui/           TypeScript + React
  sdk/python/   Python → PyPI
  sdk/node/     TypeScript → npm
  deploy/       Docker Compose, Helm
```

**Code structure: controller, service, repository.** Every backend application (gateway and server) uses the same three layers, each in its own folder and one file per feature.

| Layer | Folder / file | Does | Never does |
| --- | --- | --- | --- |
| Controller | `controllers/key_controller.py` | HTTP only: routes, request validation (schemas), auth, calls one service, maps the result to a response | SQL, Redis, business rules |
| Service | `services/key_service.py` | Business logic and rules: budgets, key rules, alert decisions | Import FastAPI, write SQL |
| Repository | `repositories/key_repository.py` | Data access only: Postgres (SQLAlchemy), ClickHouse, Redis | Business decisions |
| Client | `clients/bedrock_client.py` | Calls to outside systems: LLM providers, email, Slack | Business decisions |

Supporting folders: `schemas/` (request/response models), `models/` (database tables), `core/` (config, errors, logging), `dependencies.py` (wires repositories into services and services into controllers with FastAPI `Depends`), `jobs/` (scheduled tasks, which call services, never repositories directly).

Rules: calls only go downward (controller → service → repository or client); services depend on repository interfaces (Python `Protocol`), so unit tests run against in-memory fakes; each layer has its own test folder (`tests/controllers`, `tests/services`, `tests/repositories`). The web UI follows the same idea: `pages/` and `components/` (display) → `hooks/` (state and logic) → `api/` (HTTP calls).

## 3. Deployment


Every component runs in its own container. One command starts the whole platform on any machine with Docker: `docker compose up -d --build` (or `make up`). The Helm chart for Kubernetes runs the same images.

| Container | Image | Job | Reached at |
| --- | --- | --- | --- |
| ui | nginx (Spanport UI build) | Web UI; proxies `/api` to the server with streaming enabled | http://localhost:3000 |
| server | built from `server/` | UI API, auth, model catalog, alerts, jobs | `/api` (and port 8000) |
| gateway | built from `gateway/` | LLM gateway for apps and Claude Code | http://localhost:4000 |
| collector | OpenTelemetry Collector (contrib) | Receives traces, logs, metrics; writes to ClickHouse (or Kafka) | 4317 gRPC, 4318 HTTP |
| postgres | PostgreSQL 16 | Settings, keys, catalog | internal only |
| clickhouse | ClickHouse 24.8 | Traces, logs, metrics (logs kept 7 days) | internal only |
| redis-state | Redis 7 (`noeviction`, persisted) | Budgets, rate limits, sessions, locks, live fan-out | internal only |
| redis-cache | Redis 7 (`allkeys-lru`, not persisted) | Caches | internal only |
| caddy | Caddy 2 | HTTPS front door: certificates, security headers, routing to ui, server, gateway and collector | ports 80 and 443 (the only public ports) |
| kafka, ingester | Apache Kafka (KRaft) + collector | Optional buffer for large installs (`make up-kafka`) | internal only |

**Rules.**

- One image per application, built from the repository root so shared code (`packages/core`) is included; images run as a non-root user and have health checks.
- Services start in order using health checks (databases first, then server and gateway, then UI).
- All configuration comes from `.env` (copied from `.env.example`, never committed); the stack refuses to start without database passwords set.
- Databases are not exposed outside the Docker network; data lives in named volumes and survives restarts (`make down` keeps it, `make reset` deletes it).
- Image versions are pinned; release images are published to a container registry, signed, and shipped with an SBOM.
- Kafka is an opt-in profile, so small installs stay light.

**Quick start.**

```
cp .env.example .env          # set passwords; provider keys optional
docker compose up -d --build
```

### HTTPS front door (Caddy)

Caddy is the only container reachable from outside. It obtains and renews HTTPS certificates automatically (Let's Encrypt; a local certificate for `localhost`), redirects HTTP to HTTPS, sets security headers (HSTS, Content-Security-Policy, no framing, strict referrer) and routes requests:

| Address | Goes to |
| --- | --- |
| `https://<domain>/` | Web UI |
| `https://<domain>/api` | Server |
| `https://<domain>/v1` | LLM gateway (or a separate `gateway.<domain>`) |
| `https://<domain>:4318` | Data collector (OTLP) |

Streaming (Live, log tail, LLM answers) passes through without buffering. Requirements: a domain pointing at the server and ports 80 and 443 open. Shown in Settings → Domain and HTTPS. Secure cookies and sign-in depend on it.

## 4. Data stores and schema

Two databases: **PostgreSQL** for settings and configuration, **ClickHouse** for telemetry. This reference is generated from the live, tested schemas in `db/postgres/schema.sql`, `db/clickhouse/schema.sql` and `db/clickhouse/access.sql`. The diagram is `spanport.dbml` (dbdiagram.io).

| | PostgreSQL | ClickHouse |
| --- | --- | --- |
| Tables | 39 | 14 |
| Indexes | 103 (incl. primary and unique keys) | 14 skip indexes + sorting keys |
| Functions | 14 | 3 |
| Triggers | 43 | 5 materialized views (act like insert triggers) |

Full DDL, every index, function and trigger: `db/postgres/schema.sql`, `db/clickhouse/schema.sql`, `db/clickhouse/access.sql`; reference tables in `db/README.md`; diagram in `db/spanport.dbml` (dbdiagram.io).

### 4.1 PostgreSQL tables

| Table | Purpose | Columns | Checks |
| --- | --- | --- | --- |
| `alert_events` | Each alert: firing, acknowledged, resolved | 9 | 0 |
| `alert_recipients` | Who can receive alerts | 6 | 0 |
| `alert_routes` | Who gets which alert | 4 | 1 |
| `alert_rules` | What triggers an alert | 8 | 0 |
| `api_keys` | LLM, data, browser and admin keys (hashed) | 26 | 8 |
| `audit_log` | Who did what (read-only, 1 year) | 10 | 0 |
| `budgets` | Spend limits per key, project, client, model, end user or coding project | 14 | 3 |
| `claude_code_developers` | Everyone seen using Claude Code | 7 | 0 |
| `clients` | Who you work for | 7 | 0 |
| `coding_match_rules` | Git remote to project rules | 5 | 1 |
| `coding_project_settings` | Prompt recording and its consent | 7 | 2 |
| `data_limits` | Daily data limit, sampling, retention | 6 | 3 |
| `deploys` | Releases from CI | 8 | 1 |
| `error_groups` | Grouped errors and their status | 13 | 1 |
| `export_jobs` | Background log exports | 10 | 0 |
| `guardrail_settings` | Personal data and injection rules | 10 | 1 |
| `integrations` | CloudWatch, Loki, Elasticsearch, S3, Kafka connections | 12 | 0 |
| `job_runs` | Each job run, once-only | 9 | 2 |
| `key_model_permissions` | Models each LLM key may call | 5 | 0 |
| `model_prices` | Prices: suggested, confirmed or override | 12 | 5 |
| `models` | Models synced from providers | 13 | 1 |
| `notification_channels` | Email, Slack, Teams, PagerDuty, Opsgenie, webhook | 8 | 1 |
| `organization_settings` | Domain, sign-in options, allowed outgoing domains, exchange rate | 9 | 2 |
| `organizations` | The company running Spanport | 7 | 1 |
| `privacy_requests` | DPDP / GDPR deletions | 9 | 0 |
| `project_members` | People on a project and their role | 8 | 1 |
| `project_notification_settings` | Quiet hours, digest time | 7 | 0 |
| `projects` | A client app in one environment | 10 | 1 |
| `provider_credentials` | Provider accounts (secrets as references only) | 15 | 3 |
| `provider_reliability_settings` | Timeouts, pause rule, retries, pool size, stop on disconnect | 10 | 7 |
| `pull_cursors` | Reading position per pulled log source | 4 | 0 |
| `routing_deployments` | Where each model name goes, with weights | 7 | 1 |
| `routing_settings` | Strategy, cheaper-model routing, answer cache | 10 | 5 |
| `scheduled_jobs` | Background jobs and schedules | 4 | 0 |
| `sessions` | Signed-in browsers (cookie points here) | 9 | 1 |
| `setup_tokens` | One-time owner setup link | 5 | 0 |
| `trusted_devices` | "Trust this browser for 30 days" | 6 | 0 |
| `user_email_aliases` | Extra emails per person, e.g. their Claude sign-in | 5 | 0 |
| `users` | People who can sign in, with role | 14 | 0 |

### 4.2 PostgreSQL functions

| Function | What it does |
| --- | --- |
| `sp_alert_event_transition()` | Alert state only moves forward; sets acknowledged_at / resolved_at |
| `sp_audit_row_change()` | Writes an audit_log row for changes to sensitive tables, with secret columns removed |
| `sp_check_alias_not_primary()` | An alias cannot be another person's main email |
| `sp_current_model_price()` | Price for a model at a time: org override, then newest confirmed price |
| `sp_keep_one_owner()` | Stops removing, demoting or disabling the last owner |
| `sp_model_retire()` | Retires a model after 3 missed syncs, reactivates it when seen again |
| `sp_next_privacy_request_id()` | Generates IDs like DR-2026-0008 |
| `sp_notify_config_change()` | Sends pg_notify on sp_config_changed so every pod refreshes cached keys, budgets and rules |
| `sp_protect_audit_log()` | Blocks edits and deletes on audit_log, except the retention purge of rows older than 1 year |
| `sp_purge_expired()` | Daily clean-up of old sessions, tokens, exports, job runs and audit rows |
| `sp_revoke_sessions_on_disable()` | Disabling a person ends all their sessions and trusted browsers |
| `sp_set_updated_at()` | Keeps updated_at current on every update |
| `sp_start_job_run()` | Starts a job run; returns NULL if the job is already running anywhere |
| `sp_suspend_keys_on_archive()` | Archiving a project suspends its keys |
| `split_part()` |  |

### 4.3 ClickHouse tables and rollups

| Table | Engine | Partition | Sorted by | Kept |
| --- | --- | --- | --- | --- |
| `coding_cost_1d` | SummingMergeTree | `toYYYYMM(day)` | `org_id, project_id, user_email, day, model, cost_source` | `day + toIntervalDay(1095)` |
| `coding_cost_1d_mv` | MaterializedView → `spanport.coding_cost_1d` | | | |
| `coding_prompts` | MergeTree | `toYYYYMMDD(ts)` | `org_id, project_id, ts` | `expire_at` |
| `coding_tool_events` | MergeTree | `toYYYYMM(ts)` | `org_id, project_id, user_email, ts` | `toDateTime(ts) + toIntervalDay(395)` |
| `endpoint_stats_1m` | AggregatingMergeTree | `toYYYYMM(minute)` | `org_id, project_id, service, route, minute` | `minute + toIntervalDay(395)` |
| `endpoint_stats_1m_mv` | MaterializedView → `spanport.endpoint_stats_1m` | | | |
| `error_counts_1h` | AggregatingMergeTree | `toYYYYMM(hour)` | `org_id, project_id, fingerprint, hour` | `hour + toIntervalDay(90)` |
| `error_counts_1h_mv` | MaterializedView → `spanport.error_counts_1h` | | | |
| `error_events` | MergeTree | `toYYYYMMDD(ts)` | `org_id, project_id, fingerprint, ts` | `toDateTime(ts) + toIntervalDay(30)` |
| `feedback` | MergeTree | `toYYYYMM(ts)` | `org_id, project_id, prompt_version, ts` | `ts + toIntervalDay(395)` |
| `llm_cost_1d` | SummingMergeTree | `toYYYYMM(day)` | `org_id, project_id, client_id, key_id, day, provider, model` | `day + toIntervalDay(1095)` |
| `llm_cost_1d_mv` | MaterializedView → `spanport.llm_cost_1d` | | | |
| `llm_requests` | MergeTree | `toYYYYMM(ts)` | `org_id, project_id, ts` | `toDateTime(ts) + toIntervalDay(395)` |
| `logs` | MergeTree | `toYYYYMMDD(ts)` | `org_id, project_id, service, level, ts, id` | `toDateTime(ts) + toIntervalDay(7)` |
| `metric_points` | MergeTree | `toYYYYMM(ts)` | `org_id, project_id, name, ts` | `ts + toIntervalDay(395)` |
| `service_edges_1m` | AggregatingMergeTree | `toYYYYMM(minute)` | `org_id, project_id, from_service, to_service, minute` | `minute + toIntervalDay(395)` |
| `service_edges_1m_mv` | MaterializedView → `spanport.service_edges_1m` | | | |
| `spans` | MergeTree | `toYYYYMMDD(start_ts)` | `org_id, project_id, service, category, start_ts` | `toDateTime(start_ts) + toIntervalDay(30)` |
| `web_vitals` | MergeTree | `toYYYYMMDD(ts)` | `org_id, project_id, page, ts` | `toDateTime(ts) + toIntervalDay(30)` |

### 4.4 Redis

| Instance | Holds | Policy |
| --- | --- | --- |
| redis-state | Rate-limit buckets, budget counters (period keys such as `spend:<key>:2026-10`), session cache, job locks, live fan-out | `noeviction`, AOF persistence, alert at 70% memory |
| redis-cache | Key lookups, dashboard results, model catalog, response and semantic cache | `allkeys-lru`, no persistence |

## 5. Telemetry pipeline

### Log pipeline at scale

Spanport does not build its own log aggregator or search engine. It combines proven open-source parts and builds only the product layer on top: the ingest rules, the query translation (filter chips and text queries → SQL) and the UI.

**Pipeline.**

```
Apps (SDK)  ┐
Claude Code ├─► OTel Collector (agent per node) ─► OTel Collector (gateway tier) ─► Kafka (optional buffer) ─► ClickHouse cluster
K8s stdout  ┘      batching, memory limits            redaction, routing, sampling
```

| Stage | Choice | Job |
| --- | --- | --- |
| Collection | OpenTelemetry SDKs; OTel Collector filelog receiver (or Fluent Bit) for container stdout | Get logs off every app and node |
| Aggregation | OpenTelemetry Collector, agent + gateway tiers | Batch, compress, redact PII, add project and org labels, apply rate limits |
| Buffer (large installs) | Kafka / Amazon MSK | Absorb spikes; ClickHouse outages never lose logs |
| Storage and search | ClickHouse (sharded and replicated with ClickHouse Keeper at scale) | Index, store 7 days, search |

**Table design for fast search.**

- Partition by day; `TTL ts + INTERVAL 7 DAY` drops whole days cheaply.
- Sort key `(org_id, project_id, service, level, ts)`, so the project switcher, service and level filters and the time picker skip almost all data before reading anything.
- Data-skipping indexes: token bloom filter (`tokenbf_v1`) on `message` for word search, n-gram bloom filter where substring search is needed, bloom filter on `trace_id`, set index on `level`.
- Frequently filtered attributes (client IP, user ID, route) stored as their own columns instead of only inside the attributes map.
- ZSTD compression; logs typically compress many times over, which keeps 7 days of billions of lines affordable.
- Newer ClickHouse versions add a native full-text index; Spanport can switch to it once it is stable.

**Keeping searches to seconds at billions of lines.**

- Every search is bounded by project and time range, the two filters the sort key and partitions skip on.
- Results return newest first with a limit, so the query stops as soon as the first page is found; counts load separately.
- Long searches run asynchronously with a progress indicator instead of timing out.
- Scale out by adding ClickHouse shards; each shard searches its part in parallel.

**Sizing (to validate with load tests).** Millions of lines a day run on a single ClickHouse node; billions a day need a sharded, replicated cluster with Kafka in front. A load-test suite in `tests/load/` sets the published sizing guide.

**Alternatives considered.** Elasticsearch / OpenSearch: strongest free-text search but much higher storage and memory cost. Grafana Loki: cheap, but indexes only labels, so free-text search over billions of lines is slow. Quickwit and VictoriaLogs: purpose-built log search engines worth benchmarking later as an optional log backend.

### Span classification

Spanport never guesses what a call was: the library that made it records an OpenTelemetry span with standard attributes, and the ingest pipeline labels it from those.

**How spans are captured.** `spanport.init(ingest_key=...)` auto-instruments common libraries (FastAPI, Django, Express, psycopg, SQLAlchemy, Prisma, httpx, requests, redis, the OpenAI and Anthropic SDKs). Each call they make becomes a span with a start time, an end time and attributes.

| Label in the UI | Rule | Example attributes |
| --- | --- | --- |
| LLM | Span has `gen_ai.*` attributes, or came from the Spanport gateway | `gen_ai.system`, `gen_ai.request.model`, token counts |
| DB | Span has `db.system` | `db.system = postgresql`, `db.statement` |
| Service call | CLIENT span whose callee sends spans into the same trace under another `service.name` | `span.kind = CLIENT`, shared `trace_id` |
| External HTTP | CLIENT span whose callee does not report spans | `span.kind = CLIENT`, `server.address` |
| Incoming request | SERVER span from a web framework | `span.kind = SERVER`, `http.route` |
| Your code | Custom spans, plus the parent's self time | `@spanport.span("build_prompt")` |

**Rule order at ingest** (first match wins): LLM → DB → service call → external HTTP → incoming request → code.

**Service vs external.** The SDK adds a `traceparent` header to every outgoing request. If the receiving service also runs the SDK, its spans join the same trace, and Spanport labels the call a service call; otherwise it is external HTTP.

**Self time.** Time inside a span not covered by any child span counts as that service's own code: a 4.2 s request with 3.8 s of child spans shows 0.4 s of code.

**LLM confirmation.** Calls routed through the gateway carry the app's trace ID, so the gateway's span (exact tokens, cost, provider, fallbacks) attaches to the right request even when the app's LLM SDK is not instrumented.

### Model catalog sync

The list of models a key can use is fetched from each provider, not typed in by hand, so new models and versions appear on their own.

**Sources.** One fetcher per provider, run with the credentials saved in Providers:

| Provider | Call | Returns |
| --- | --- | --- |
| OpenAI | `GET /v1/models` | Model IDs, created date |
| Anthropic | `GET /v1/models` (paginated) | Model IDs, display names |
| AWS Bedrock | `list_foundation_models` and `list_inference_profiles`, per region | Model IDs, provider, modalities, lifecycle status |
| Google Gemini | `GET /v1beta/models` (paginated) | Model names, versions, token limits, supported methods |

**Schedule.** Every hour per provider credential and region, plus on demand from the Refresh button on the Create key page.

**Normalization.** A rules file of per-provider patterns splits each model ID into family, version and kind (chat or embedding), e.g. `claude-sonnet-5-5` → Claude Sonnet, 5.5. Dated snapshot suffixes become sub-versions. IDs that match no rule are still listed, under Other.

**Versions on keys.** A key can allow a family's `latest` alias, which resolves to the highest active version after every sync, or pin exact versions. Production keys should pin; new versions never change a pinned key.

**Lifecycle.**

- New model or version: stored with `first_seen`, shown with a NEW badge, Slack notification. Never added to existing keys unless they use `latest`.
- Deprecated: from Bedrock's LEGACY status or the maintained catalog file; still callable, shown with a DEPRECATED badge.
- Retired: missing from the provider's list for 3 syncs in a row; blocked for new requests, kept for historical traces and cost reports.

**Gaps the provider APIs leave, and how they are filled.**

- Prices: none of the APIs return them. Spanport ships a pricing file in the repository, updated each release, with per-org overrides. Models without a price are flagged PRICE NOT SET so budgets are not silently under-counted.
- Bedrock access: listing shows what exists in the region, not what the account may call; access is confirmed before a Bedrock model is marked usable.
- Sync failures: the last known list is kept and the error is shown per provider (e.g. "Sync failed for Gemini: 401").

### Integrations

Spanport connects to the log tools teams already use. Each project configures its own integrations in Integrations (per-project settings; credentials stored as references to the secrets manager, never in plain text).

| Kind | What it does | How | Release |
| --- | --- | --- | --- |
| Send copies out | Forward logs to other systems for long-term retention, compliance or existing dashboards | OpenTelemetry Collector exporters in the gateway tier, after PII redaction | v1.0 |
| Pull logs in | Bring logs that already live elsewhere into Spanport | Collector receivers, or existing shippers sending OTLP | v1.0 |
| Search in place | Search another system from the Logs screen without copying | Log source adapters in the server's repository layer | v1.0 |

| Target | Send copies out | Pull logs in | Search in place |
| --- | --- | --- | --- |
| AWS CloudWatch Logs | `awscloudwatchlogs` exporter (IAM role, one log group per project) | `awscloudwatch` receiver polls selected log groups | CloudWatch Logs Insights query |
| Grafana Loki | Loki's native OTLP endpoint (`otlphttp` exporter, tenant header) | Grafana Alloy sends OTLP to Spanport | LogQL |
| Elasticsearch / OpenSearch (ELK) | `elasticsearch` exporter (index per project) | Fluent Bit, Vector or Logstash send OTLP to Spanport | Elasticsearch query DSL |
| Amazon S3 archive | `awss3` exporter (compressed, partitioned by day) |: | Athena (later) |
| Kafka / Amazon MSK | `kafka` exporter | `kafka` receiver |: |

**Per-integration settings.** On/off, what to send (all logs, WARN and above, ERROR only), destination fields (region and log group, endpoint and tenant, index, bucket and prefix, brokers and topic), credential reference, status (last sent, errors) and a Test connection button that writes one test line.

**How configuration reaches the collector.** Integration settings are stored in Postgres. The server renders the collector gateway-tier pipeline from them and reloads the collectors (file + reload in v1.0; OpenTelemetry OpAMP remote configuration later). Forwarding runs entirely in the collector, so it never adds latency to apps or the gateway.

**Search-in-place adapters.** A `LogSource` interface in `repositories/log_sources/` with one adapter per backend: `clickhouse_source.py` (default), `cloudwatch_source.py`, `loki_source.py`, `elasticsearch_source.py`. Each translates the same filter-chip query tree into its own language. A Source selector on the Logs screen picks the backend. Limits: speed and cost depend on the backend (CloudWatch Insights is asynchronous and billed per GB scanned; Loki is slow at free-text over long ranges); live tail and the SQL preview work only on Spanport's own store; trace links work only when external logs carry a trace ID.

**Security.** Least-privilege credentials per integration (e.g. `logs:PutLogEvents` on one log group, `s3:PutObject` on one prefix); PII redaction happens before export; every integration change is audit-logged.

Traces can follow the same pattern later (AWS X-Ray, Grafana Tempo, Jaeger).

## 6. Real-time streaming


Spanport streams with Server-Sent Events (SSE), not WebSockets.

| Place | Direction | Technology |
| --- | --- | --- |
| LLM responses through the gateway | Provider → gateway → app | SSE, in the OpenAI and Anthropic formats, so their SDKs work unchanged |
| Live screen (requests, per-API cards, live logs) | Server → browser | SSE (`EventSource`) |
| Logs live tail | Server → browser | SSE |
| Apps and SDKs sending traces, logs and metrics | App → collector | OTLP over HTTP or gRPC |
| Everything else (search, keys, settings, exports) | Request → response | REST over HTTP |

**Why SSE.** Data flows one way (server to browser); it is plain HTTP, so it passes load balancers, proxies, the AWS ALB and Kubernetes ingress without upgrade handling and uses the normal session cookie; browsers reconnect automatically and send `Last-Event-ID`, so streams resume without gaps; and it matches the gateway's LLM streaming, so there is one technology to run and debug.

**Rules.**

- Serve over HTTP/2, so several open tabs do not hit the browser's per-site connection limit.
- Fan out across server pods with Redis pub/sub: each event is published once, and every pod pushes it to its own connected browsers.
- Send a heartbeat every 15 seconds so idle proxies keep the connection open.
- Turn off proxy buffering on streaming routes (e.g. `X-Accel-Buffering: no`).
- Close the browser `EventSource` when the screen unmounts or the project changes.

WebSockets would only be added for a genuinely two-way feature (for example, people editing the same view together); nothing in v1.0 needs one.

## 7. API design

**Structure.** Tests, review

**Surfaces.**

| Surface | Path | Auth | Format |
| --- | --- | --- | --- |
| LLM gateway | `/v1/chat/completions`, `/v1/messages`, `/v1/embeddings` (OpenAI and Anthropic compatible) | LLM key in `Authorization` | JSON, SSE streaming |
| Telemetry ingest | Collector `:4317` (gRPC), `:4318` `/v1/traces`, `/v1/logs`, `/v1/metrics` (HTTP) | Data or browser key | OTLP (protobuf or JSON) |
| Management API | `/api/v1/...` (keys, projects, providers, alerts, logs, traces, costs, storage, settings) | Session cookie (UI) or admin key | JSON; problem+json errors |
| Live streams | `/api/v1/live`, `/api/v1/logs/tail` | Session cookie | SSE |
| Health and metrics | `/health`, `/ready`, `/metrics` on every component | None (internal network) | JSON, Prometheus |

**Errors.** RFC 9457 problem details (`application/problem+json`) with a stable `code` and `request_id`.

### Rate limiting

Token buckets in Redis, checked with one atomic Lua call (one network round trip), shared by every gateway and server pod. Code: `packages/core/spanport_core/ratelimit.py`.

| Where | Limit | Why |
| --- | --- | --- |
| Gateway (LLM keys) | Requests and tokens per minute per key (set on Create key), per end user, and a maximum of concurrent requests per key | Stops runaway scripts and single users from using a whole key |
| Server API | About 300 requests a minute per signed-in user and 600 per admin key; log search 30 a minute with at most 3 running per user; exports 5 running per project; model refresh 6 a minute; privacy deletions one at a time | Protects ClickHouse and keeps the UI fast for everyone |
| Sign-in | 5 failed attempts per account and per IP in 15 minutes, then increasing waits; the same for two-step codes and the setup link | Stops password guessing |
| Ingest (collector) | Per data key: events per second plus the daily data limit; browser keys also per visitor IP | One noisy app cannot flood others; apps are never blocked, extra data is dropped and the SDK backs off |

**Responses.** Every limited endpoint returns `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`. When a limit is hit: HTTP 429 with `Retry-After` and a JSON body (`error: rate_limited`, which limit, a plain-language message, `retry_after_s`). The UI waits `Retry-After` before retrying and says so.

**When Redis is unavailable.** Rate limits fail open (requests continue, an alert fires); budgets fail closed using the last known spend, so nobody overspends. Provider 429s (for example Bedrock throttling) trigger the fallback to another deployment.

### Pagination

Cursor (keyset) pagination on every list. Code: `packages/core/spanport_core/pagination.py`.

- Request: `?limit=50&cursor=<next_cursor>`. Default 50, maximum 200 (logs: 100, maximum 1,000).
- Response: `{"data": [...], "next_cursor": "...", "has_more": true}`; the cursor is opaque (the last row's sort key, e.g. timestamp and ID, encoded). An invalid cursor returns 400 `invalid_cursor`.
- Queries use `WHERE (ts, id) < (cursor) ORDER BY ts DESC, id DESC LIMIT n + 1`, never `OFFSET`: fast at any depth and correct while new rows arrive.
- Totals for large data are separate and approximate ("about 12,400 matching lines") so the first page never waits for a full count.
- Small lists (keys, people, projects) use the same format for consistency.

## 8. Security

### Authentication and access

**First-time setup.** On first start with no users, the server prints a one-time setup link (valid 1 hour, single use) in its logs. Opening it creates the Owner account (name, email, password, organization name); the token is then destroyed and `/setup` stops working. Automated installs can set `SPANPORT_OWNER_EMAIL` and `SPANPORT_OWNER_PASSWORD_FILE` (a mounted secret file) instead.

**Login.**

- Email and password, hashed with Argon2; two-factor authentication (authenticator app) available and can be required for Owner and Admin.
- Sign in with Google (OpenID Connect); admins can turn off password login once everyone uses Google.
- The browser receives a secure, HTTP-only session cookie that expires after inactivity. API keys are never used to log in to the UI.
- Roles: Owner, Admin, Member, Viewer. Only Owner and Admin manage users, providers and admin keys; Viewer cannot export logs.

**Admin keys (`sp_admin_…`).** Created by an Owner or Admin from API keys → Create key → Admin key, for scripts and CI. Each key has scopes (e.g. `keys:write`, `budgets:write`, `projects:read`, `logs:read`), an expiry of at most 90 days and an optional IP allowlist. Shown once and stored as a hash. An admin key cannot create a key with more power than itself or change user roles, and every action it takes is written to the audit log.

**Recovery.** Someone with server access can run `spanport admin reset-password --email <email>` inside the container.

**Claude Code identity.** Developers are identified per person, not per machine. With telemetry only, Claude Code's identity attributes (account, email when signed in, session) create the developer entry automatically on first data; the org adds its ingest key and optional labels such as `team` through managed settings. Through the gateway, each developer uses a personal virtual key, which is their identity; developers can get it themselves after SSO login ("Get my Claude Code key"). One person's laptops, remote machines and parallel sessions are grouped under that person; CI and bots use separate service keys.

### Cookies and sessions

The web UI uses only strictly necessary cookies: no tracking or marketing cookies, so no consent banner is needed.

| Cookie | Purpose | Settings | Lifetime |
| --- | --- | --- | --- |
| `__Host-sp_session` | Keeps the user signed in; holds a random session ID only (stored hashed in `sessions`) | `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/` | Until sign-out or the idle timeout (8 hours by default, set in Settings → Sign-in) |
| `__Host-sp_csrf` | Cross-site request forgery protection for state-changing actions (double-submit token sent in a header) | `Secure`, `SameSite=Strict`, readable by the UI | Same as the session |
| `__Host-sp_oauth` | Google sign-in `state` and PKCE values during the redirect | `HttpOnly`, `Secure`, `SameSite=Lax` | 10 minutes; deleted after sign-in |
| `__Host-sp_2fa_trusted` (optional) | "Trust this browser for 30 days" for the two-step code | `HttpOnly`, `Secure`, `SameSite=Strict` | 30 days; cleared when the password changes |

**Rules.**

- The `__Host-` prefix makes the browser enforce `Secure`, no `Domain` and `Path=/`, so subdomains cannot overwrite the cookies.
- Sessions can be revoked instantly: sign-out deletes the cookie and revokes the session row; "Sign out everywhere" revokes all of a user's sessions; disabling a user revokes theirs.
- Never stored in cookies or browser storage: API keys of any type, session tokens in `localStorage`. Preferences such as timezone are saved in the user's settings on the server.
- The gateway, SDKs and collector authenticate with keys in headers only and set no cookies.
- The browser SDK inside customers' web apps sets no cookies (it keeps a session ID in memory or `sessionStorage`), so it does not add consent requirements to those apps.
- Live and log-tail streams (SSE) are authenticated by the session cookie automatically, because `EventSource` sends cookies to the same site.

### Sessions, not JWT

The web UI uses server-side sessions: a random ID in an HttpOnly cookie, Postgres as the source of truth, Redis as a cache. This allows instant sign-out, "sign out everywhere", disabling a person and role changes taking effect on the next click. Google sign-in's ID token (a JWT) is verified once at sign-in and never used afterwards. Apps, SDKs and CI use Spanport keys (random, stored hashed, revocable instantly), not JWTs.

### Outgoing requests (SSRF protection)

Some features make Spanport connect to an address a user typed. Each one goes through a shared URL guard so it cannot be pointed at private networks or cloud metadata.

| Feature | Who connects | Protection |
| --- | --- | --- |
| Webhook and Microsoft Teams alert channels | Server (job worker) | URL guard at save and send time; signed payloads |
| Loki and Elasticsearch endpoints (send copies, search in place) | Server and OTel Collector | URL guard before saving and before collector configuration is written |
| Kafka brokers | OTel Collector | Host and port checked by the same guard; TLS ports only |
| SMTP server | Server | Guard plus admin-only setting |
| Read-only SQL box | ClickHouse | Restricted user without url, s3, remote or file table functions; `remote_url_allow_hosts` empty; row policies |
| PDF invoice reports | PDF renderer | Rendered with network access off; bundled fonts and logos only |
| Image URLs in prompts | Gateway, only if it must download an image | Same guard and size limits; otherwise passed through to the provider |
| Bedrock region, S3 bucket, CloudWatch log group | Server and collector | Checked against allowed formats; no custom endpoints |

**URL guard rules.** `https://` only on port 443 (or admin-allowed ports); no usernames or passwords in URLs; domain names, not raw IPs; every resolved address must be public (blocks 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16 including 169.254.169.254, 100.64/10, 0/8, multicast, `::1`, `fc00::/7`, `fe80::/10` and IPv4-mapped forms); DNS is resolved again at send time and the connection is made to the checked address while TLS still verifies the real hostname (stops DNS rebinding); redirects are not followed; 3-second connect and 10-second total timeouts; at most 64 KB of response read; only the status code is shown to users, never the body. Admins can add an allow-list of destination domains.

**Webhook signing.** Every webhook carries `X-Spanport-Signature: t=<timestamp>,v1=<HMAC-SHA256(secret, timestamp + body)>` so receivers can verify it and reject replays.

**Network defence.** On AWS, IMDSv2 with hop limit 1 and IAM roles for service accounts; egress rules let the server, collector and job workers reach the internet and their own databases only, nothing else inside the network.

## 9. Reliability

### Stopping LLM calls when the caller disconnects

When a user closes the page or clicks Stop mid-answer, the provider would otherwise keep generating and bill every token. The gateway detects that its caller (your app) has gone and closes its connection to the provider, which stops the generation.

- **Detection:** the connection close is reported by the gateway's web server ("client disconnected"); while streaming, the next write fails; for non-streaming calls the gateway checks about once a second; a 15-second heartbeat catches dropped mobile connections.
- **Result:** the call is recorded as "stopped early: caller disconnected" with only the tokens produced; Costs shows "Saved by stopping abandoned answers".
- **What apps must do:** cancel their request to Spanport when the user leaves (for example pass `req.signal` / an `AbortController` to the OpenAI or Anthropic SDK). Setup guides and Getting started include this line for each language.
- On by default; switch in Providers → "Stop the provider when the app disconnects".

### Provider timeouts, circuit breakers and retries

| Protection | Default | Purpose |
| --- | --- | --- |
| Connect timeout | 5 s | Do not wait forever for a provider to answer the connection |
| First-token timeout | 30 s | Give up on a stalled answer and use the fallback |
| Circuit breaker | Pause a deployment when 50% of calls fail within 30 s; pause 30 s; then a few test calls decide | Stop sending traffic to a failing provider and use the fallback immediately |
| Retry budget | Retries at most 10% of normal traffic | Retries cannot multiply load during an outage |
| Connection pool | 100 open connections per provider | Faster calls, no new handshake each time, bounded resources |

Each provider shows its traffic state (working, paused and sending to backup, testing) on the Providers screen; all values are adjustable there.

### Scheduled jobs (run once)

Background work runs through a job queue (arq on redis-state) with a lock, so each scheduled job runs exactly once even with several server pods. Failed runs retry 3 times with backoff, then wait in a "failed" list for a person (Retry / Dismiss). If redis-state is down, jobs wait rather than run more than once.

| Job | Schedule |
| --- | --- |
| Model sync | Every hour |
| Nightly backup | Daily 03:00 UTC |
| Email digests | Daily, per project time |
| Data-limit check | Every 5 minutes |
| Rollups | Every minute |
| Error grouping | Every minute |
| CloudWatch pull | Every minute |
| Retention check | Daily 04:00 UTC |

Shown in Settings → Scheduled jobs with last run (time, duration, result, which server), next run and Run now.

### Failure modes and recovery

| Component down | What keeps working | What degrades | Recovery |
| --- | --- | --- | --- |
| redis-cache | Everything | Key lookups and dashboards slower (served from in-process cache, then Postgres); answer cache skipped, so LLM cost rises slightly | Refills automatically |
| redis-state | LLM calls for keys well under budget; sign-in (sessions in Postgres) | Rate limits fail open (alert sent); keys above 95% of budget paused (budgets fail closed using last known spend); revoked keys stop within 30 s instead of 1 s; scheduled jobs wait; Live polls every 5 s | Replica failover (ElastiCache Multi-AZ or Sentinel); AOF restores counters |
| ClickHouse | LLM calls, keys, budgets, Live | Logs, traces, history screens unavailable (banner shown); data buffered in the collector disk queue or Kafka; alerts that read telemetry paused, with a system alert | Replica (ClickHouse Keeper); buffered data replays |
| Postgres | Existing keys from cache for a while | New keys and setting changes stop | RDS Multi-AZ failover; nightly backups |

Targets: RPO 0 with Kafka, under 5 minutes without; RTO under 5 minutes with replicas. Readiness checks are per component, so the gateway stays ready when ClickHouse is down.

## 10. Performance and capacity


The gateway must add almost no latency and must keep serving if the observability side is down.

| Area | Target |
| --- | --- |
| Gateway overhead | < 15 ms p95 added latency (non-streaming), < 5 ms to first byte for streaming |
| Gateway availability | 99.9%; tracing pipeline failure never blocks requests |
| Throughput | 500 req/s per gateway pod at MVP; scale horizontally |
| Telemetry delay | Traces and logs visible in UI within 10 s |
| Caching | Key lookups above 99% hit ratio; zero evictions on redis-state; revoked keys stop within 1 second |
| API rate limits | Gateway per key / end user; server 300 a minute per user, 600 per admin key; 429 with Retry-After |
| Lists | Cursor pagination, 50 per page by default (max 200; logs max 1,000), fast at any depth |
| UI first load | Per-screen code splitting; only the opened screen and its libraries load |
| Log export | 100,000 lines: starts < 2 s, completes < 15 s p95 on 20 Mbps; background exports up to 10 million lines / 2 GB |
| Retention | Metrics 13 months; traces 30 days default, configurable; logs 7 days maximum; prompt bodies 7 days default |
| Data residency | Region selectable; India region (ap-south-1) available |
| Deployment | Self-hosted, everything in containers: `docker compose up` starts all components on one machine; the Helm chart runs the same images on Kubernetes |
| Security | TLS everywhere, secrets encrypted at rest, tenant isolation on every query |
| Compliance | Data stays in the user's own infrastructure; DPDP-friendly by design |

### Caching

Two Redis instances with different jobs, plus a small in-process cache in each gateway and server pod. Code: `packages/core/spanport_core/cache.py`.

| | redis-state | redis-cache |
| --- | --- | --- |
| Holds | Rate-limit buckets, budget counters, sessions, locks | Key lookups, dashboard results, model catalog, response and semantic cache |
| When memory is full | Never evicts (`noeviction`); alert at 70% memory | Evicts least-recently-used keys (`allkeys-lru`) |
| Persistence | On (AOF), backed up | Off: losing it only makes requests slower |

**Classic cache problems and how Spanport handles them.**

| Problem | Where it would hit | Protection |
| --- | --- | --- |
| Stampede: a hot key expires and many requests rebuild it at once | Gateway key lookups for busy keys, Home and APIs dashboards, model catalog | Single-flight in each pod (one load, everyone shares the result) plus a short cross-pod lock (`SET NX PX`); early refresh in the last 10% of a key's life |
| Avalanche: many keys expire together | Budget counters at the start of a day or month; caches warmed together after a deploy | TTL jitter of ±15% on every cached value; budget and limit counters use period keys (`spend:<key>:2026-10`) that start fresh automatically and are deleted days later at staggered times |
| Penetration: repeated lookups of things that do not exist | Leaked, revoked or made-up API keys | Negative caching ("this key is invalid") for about 60 seconds, plus per-IP rate limits |
| Redis down | Every request falls through to the databases | In-process L1 cache in front of Redis; rate limits fail open, budgets fail closed |
| Stale data after a change | Revoked keys, changed budgets or guardrails | `invalidate()` deletes the Redis copy, clears the local copy and publishes to every pod over Redis pub/sub; local copies live at most 30 seconds anyway. A revoked key stops within a second |
| Duplicate expensive work | The same prompt sent many times at once | Request coalescing in the gateway: identical concurrent prompts make one provider call and share the answer |
| Reconnect herds | Browsers reconnecting SSE streams or retrying after a restart | Exponential backoff with full jitter on reconnects and retries |
| Big or hot keys | Semantic cache entries; one very busy key | Size limit and compression for cached answers, per-project namespaces, L1 for the hottest keys |

**Typical lifetimes.** Key lookups: 5 minutes in Redis, 30 seconds locally, invalidated instantly on change. Invalid-key results: 60 seconds. Dashboard queries: 30–60 seconds. Model catalog: until the next hourly sync. Response cache: per project setting (1 hour, 1 day or 7 days). All with ±15% jitter.

**Monitoring.** Hit ratio per cache (key lookups above 99%), evictions (must stay 0 on redis-state), memory use and latency, shown in Settings → Backups and health and on `/metrics`, with alerts when the hit ratio drops or evictions start.

## 11. Storage management


An owner-only Storage screen (Setup → Storage) shows what is kept in Redis and ClickHouse and removes what is no longer needed, without risking budgets, limits or other clients' data. API: `/api/v1/storage/...`; code: `repositories/redis/storage_admin_repository.py`, `repositories/clickhouse/storage_delete_planner.py`, `services/storage_service.py`.

| Store | What you can see | What you can delete | Never |
| --- | --- | --- | --- |
| redis-cache | Groups (API key lookups, dashboard results, model catalog, saved answers, live buffers) with key count, memory and lifetime; browse and search key names with type, expiry and size | One key, or a whole group ("Clear all"); it is rebuilt on the next request | Showing values (some contain key details) |
| redis-state | Memory, evictions (must be 0), persistence; counts of budget counters, rate-limit buckets, sessions and job locks | Reset one key's rate-limit counters (with a reason); release a stuck job lock | Deleting budget counters (a key could overspend) or bulk-deleting anything; sessions are ended from People and roles |
| ClickHouse | Disk used, each table's rows, size, oldest data and retention | One project's data for a date range (background delete); whole days for all projects (instant, by dropping daily partitions, for a nearly full disk); sample data | Future dates, ranges over 400 days, tables outside the allow-list |

**Safety rules.**

- Owner role only; every call is rate-limited (60 a minute) and written to the audit log with who, what and how much.
- Redis is browsed with `SCAN` (never `KEYS *`) and deleted with `UNLINK` in batches of 500, so Redis is never blocked; only registered key groups are visible.
- ClickHouse deletions show a preview first (rows and size), then require typing the project ID (or `all-projects`); statements are parameterized and always scoped to the organization.
- Retention still runs automatically every night; this screen is for exceptions (sample data, a decommissioned project, a disk emergency). Privacy requests (Settings) use the same delete path.
- Storage settings shown on the screen: retention per ClickHouse table (logs at most 7 days), Redis memory limits for state and cache, ClickHouse disk use (alert at 80%), redis-state memory (alert at 70%) and evictions (alert on any).

## 12. Frontend architecture

### Lazy loading

- **Per-screen code splitting:** every screen is a `React.lazy` chunk loaded when first opened; hovering a sidebar link preloads it.
- **Heavy libraries on demand:** charts, the service map and stack-trace highlighting load only on screens that use them.
- **Details on click:** a log line's fields, a request's steps and logs, an error's stack trace and a key's recent requests are fetched when expanded, not with the list.
- **Infinite scroll with virtualization:** Logs, Live history, Errors and the audit log use TanStack Query `useInfiniteQuery` following `next_cursor`; the next page loads shortly before the end of the list; TanStack Virtual renders only visible rows.
- **Important things first:** Home shows the broken / slow / spend answers first, then recent deploys and health.
- **Caching:** results stay fresh for about 30 seconds, so moving between screens does not refetch everything; hidden tabs pause refreshing.

### Frontend engineering rules

The web UI is React + TypeScript, organized as pages and components (display) → hooks (logic and state) → api (HTTP calls).

| Need | Use | Don't |
| --- | --- | --- |
| Server data (keys, APIs, logs search, costs, errors, models) | TanStack Query (`useQuery`, `useMutation`), with filters, project and time range in the query key | Hand-written `useEffect` fetching: it causes race conditions and has no caching |
| Live streams, timers, browser APIs | `useEffect` that always returns a cleanup (close the stream, clear the timer) | Effects without cleanup: they leak connections and double-connect in development |
| Measuring or adjusting layout before the screen paints (keep the Live list's scroll position steady when new rows are added above, place a tooltip or dropdown inside the visible area) | `useLayoutEffect`, short and with cleanup | `useLayoutEffect` for anything else: it blocks painting and makes the UI feel slower |
| DOM access, open connections, timer IDs, live-event buffers, latest handler values | `useRef` | Anything shown on screen in a ref: changing `ref.current` does not re-render |
| Heavy calculations over hundreds or more items already in the browser (per-API cards over the last 60 seconds, big table sorts, chart data) | `useMemo` | Wrapping simple values; heavy aggregates over long ranges belong on the server (ClickHouse) |
| Grouping data already in the browser (Live per-API cards, level counts, grouping by API) | Built-in `Map.groupBy` (non-string keys, keeps order) or `Object.groupBy` (string keys), inside `useMemo` | lodash or hand-written groupBy helpers; grouping large data in the browser: aggregate it in ClickHouse with `GROUP BY` |
| Values derived from other state (totals, percentages, filtered lists) | Compute during render | Storing them in state and syncing with effects |
| Reacting to a click (export, revoke, refresh) | Event handler or `useMutation` | An effect watching a flag |
| Long lists (Live, Logs, Errors) | Virtualized rendering (TanStack Virtual) | Rendering thousands of rows |

**`useEffect` checklist.** Every effect in the UI follows these rules (reviewed in pull requests):

1. **Only to sync with something outside React:** streams (SSE), timers, browser APIs (`ResizeObserver`, `visibilitychange`, keyboard shortcuts), the page title, non-React widgets. Not for data loading (TanStack Query), derived values (compute in render) or reacting to clicks (event handlers).
2. **Always return a cleanup** that undoes exactly what the effect did: close the `EventSource`, `clearInterval` / `clearTimeout`, `removeEventListener`, `disconnect()` observers, abort requests.
3. **Safe to run twice.** React's development mode mounts, cleans up and mounts again; the effect must work the same way (no duplicate streams, no double subscriptions).
4. **Complete dependency arrays.** ESLint `react-hooks/exhaustive-deps` is on and is never silenced; if a dependency causes unwanted re-runs, fix the cause instead.
5. **Stable, simple dependencies.** Depend on IDs and primitive values (`projectId`, `filtersKey`), not objects or functions recreated every render; move helper functions inside the effect.
6. **Latest values without re-subscribing.** Long-lived effects read the newest handler or filter through a ref (or `useEffectEvent` where the React version supports it), so a stream is not reopened on every render.
7. **Functional state updates** inside timers and stream handlers (`setRows(r => …)`), so they never work with stale state.
8. **No async effect callbacks.** Define an async function inside the effect and call it; ignore or abort results after cleanup.
9. **No unconditional state updates** inside an effect that depends on that state (prevents render loops).
10. **One effect per concern,** wrapped in a named custom hook in `hooks/` (`useLiveStream`, `useInterval`, `useResizeObserver`, `usePageVisibility`, `useKeyboardShortcut`).
11. **Handle failures:** streams reconnect with backoff and show their status (Live, Reconnecting…, Paused).
12. **Save resources when hidden:** pause polling and live updates while the browser tab is hidden, and resume when it is visible again.

**Live updates are batched.** Incoming events are collected in a `useRef` buffer and flushed to state about every 250 ms, so hundreds of events a second cause about four re-renders a second, not hundreds.

**Grouping in the browser.** Use the built-in `Map.groupBy` / `Object.groupBy` (ES2024), only on data already on screen; anything over long ranges or many rows is aggregated by ClickHouse (`GROUP BY`). Requires TypeScript 5.4+ with `"lib": ["ES2024"]`; for browsers older than Chrome/Edge 117, Firefox 119 or Safari 17.4, add the core-js polyfill. `Object.groupBy` returns an object without a prototype, so read it with `Object.keys` / `Object.entries`. In Python, use `collections.defaultdict(list)` (not `itertools.groupby` unless the data is sorted).

```ts
const apiStats = useMemo(() =>
  [...Map.groupBy(events, (e) => e.route)].map(([route, evs]) => ({
    route,
    count: evs.length,
    p95: percentile(evs.map((e) => e.durationMs), 0.95),
  })),
[events]);
```

**Checks.** ESLint `react-hooks/rules-of-hooks` and `react-hooks/exhaustive-deps` run in CI; performance work starts from the React DevTools Profiler; if the React Compiler is adopted, manual `useMemo` stays only where profiling shows a need.

### Visual design rules

Spanport must look like a deliberately designed monitoring tool, not a generated template.

| Rule | Detail |
| --- | --- |
| Theme | Dark graphite only. No white or near-white surfaces and no purple anywhere |
| Colors | Page `#0F1216`, cards `#171B21`, inputs and raised areas `#1D222A`, borders `#2A313B`, dividers `#232931`; text `#E6E9EE`, secondary `#9AA4B2`, muted `#7C8796`; one accent, signal teal `#2BA89A` for primary buttons and selection (`#5CC8BB` for links); status red `#F0705E`, amber `#E9A23B`, green `#4CC38A`; chart series `#D98E3A`, `#5BA4E6`. Text on teal, red or green buttons is dark `#0B0E11` |
| Shapes | Buttons, inputs, tabs and status tags use small corners (4 to 8 px). No pill-shaped buttons or tags |
| Words | Every label says exactly what happens or what it is: verb plus object ("Open POST /chat errors", "Revoke key", "Reset rate limit"). Numbers carry units and a comparison with normal ("1.9% fail, normally under 0.5%"). No vague text ("Look into it", "Learn more", "Something went wrong"), no marketing words ("seamless", "powerful", "magic") |
| Characters | No emoji. No em dashes: use a colon, comma or full stop, and "n/a" or "Not set" for empty values. Plain arrows and dots only where they carry meaning |
| Motion | No scroll animations, parallax, fade-ins or decorative motion. State changes are instant; at most a short (under 150 ms) feedback transition, and none when the user prefers reduced motion |
| Type scale | Six sizes only, base 14 px with a ratio of about 1.25: `--text-xs` 12 (captions, table meta, chart labels), `--text-sm` 13 (dense tables, secondary text), `--text-md` 14 (body, form fields), `--text-lg` 18 (section titles), `--text-xl` 22 (card values, panel titles), `--text-2xl` 28 (page titles, Home headline numbers). A value is shown about 1.6 times larger than its label |
| Spacing | Eight steps on a 4 px grid, growing about 1.5 times per step: `--space-1` 4, `--space-2` 8, `--space-3` 12, `--space-4` 16, `--space-5` 24, `--space-6` 32, `--space-7` 48, `--space-8` 64. Padding, margins and gaps use only these; borders, control heights (44 px) and chart geometry are not spacing |
| Layout split | A main area with a side panel shares space in the golden ratio, about 62% and 38% (`--split-main` 1.618 to `--split-side` 1), and stacks on narrow screens |
| Tokens | Colors, type sizes, spacing and radii are defined once as CSS variables; screens use only token values, never their own numbers |

## 13. Engineering standards


Ten rules keep the codebase clean as features grow. Full detail: `docs/engineering/rules.md` (also summarized for AI coding assistants in `CLAUDE.md`).

| # | Rule | What it means in Spanport | Enforced by |
| --- | --- | --- | --- |
| 1 | Clean folder structure | Backend: controllers, services, repositories, clients, schemas per app; shared code in `packages/core`. UI: one folder per feature (`features/<feature>/components, hooks, api.ts`), shared parts in `components/ui` and `lib` | Review; file-size guideline |
| 2 | Business logic separate from UI | Controllers only handle HTTP; rules live in services. UI components only display; data and rules live in hooks and pure `lib` functions; components never call `fetch` | import-linter, ESLint restricted imports |
| 3 | No duplicate or dead code | Unused code, exports, files and dependencies fail the build; copy-paste is detected; no commented-out code; flags removed after release | ruff, vulture, ESLint, knip, jscpd in CI |
| 4 | Consistent naming | snake_case Python and JSON, PascalCase classes and components, `useX` hooks, `/api/v1/` plural kebab-case paths, `SPANPORT_` env vars, Conventional Commits | Linters, review |
| 5 | Proper error handling | RFC 9457 problem details with stable codes and request IDs; domain exceptions mapped in one place; no stack traces to users; no swallowed errors; timeouts on every outside call; loading, empty, error and outage states on every screen | Tests, review |
| 6 | Environment config separate from code | Typed settings validated at start-up; only `.env.example` committed; secrets from a secrets manager; no hard-coded URLs or limits; browser gets runtime config from `/api/v1/config` | Secret scanning, start-up validation |
| 7 | Modular, reusable components | Shared UI kit (Button, Card, Table, Tabs, FilterChips, TimeRangePicker, ProjectSwitcher, StatusPill, CodeBlock, ConfirmPanel, EmptyState, ErrorState, Banner) and shared backend helpers; design tokens defined once | Review |
| 8 | Proper state management | Server data in TanStack Query; filters, time range, project and tab in the URL; small global store (Zustand) for timezone and theme; forms with React Hook Form + zod; one home per piece of state | Review |
| 9 | Documented codebase | README per app and package; docstrings and TSDoc on public code; comments explain why; ADRs, PRD, BRD and runbooks; OpenAPI generated with examples; changelog from commits | CI checks the OpenAPI spec |
| 10 | Scalable API structure | `/api/v1` versioning; one router per domain; separate request, response and storage models; resource-style routes; cursor pagination; auth, rate limit and error format on every endpoint; idempotency keys; 202 + job ID for long tasks; request IDs; async I/O and pools | Tests, review |

## 14. Testing and CI

| Layer | What | Tools |
| --- | --- | --- |
| Unit | Services, pure functions, pagination, rate limiting, caching, URL guard | pytest, Vitest |
| Database | Schema loads; behaviour tests for every function, trigger and constraint (`db/postgres/tests.sql`); ClickHouse rollups (`db/clickhouse/test_schema.py`) | PostgreSQL 16, ClickHouse |
| Integration | Full stack in containers: gateway, server, collector, databases | Docker Compose or Testcontainers in CI |
| Contract | Each provider adapter against recorded provider responses | pytest with recorded fixtures |
| Isolation | One organization can never read another's data (API and SQL box) | Dedicated test suite |
| UI | Key flows on every page | Playwright |
| Load | Gateway overhead under 15 ms at p95; ingest throughput | k6 or Locust |

**Pipeline:** lint (ruff, ESLint) → types (mypy, tsc) → layering and dead-code checks (import-linter, knip, vulture, jscpd) → tests → build images → scan (Trivy) → sign (cosign) → SBOM (syft) → publish to PyPI, npm and the container registry on release. Versions follow semantic versioning; the changelog is generated from Conventional Commits.

## 15. Build order


All seven modules ship in v1.0; this is the order to build them in, each step usable before the next starts.

1. **Gateway core**: OpenAI- and Anthropic-compatible endpoints, adapters for OpenAI, Anthropic, Bedrock and Gemini, virtual keys, retries and fallbacks, model catalog sync.
2. **Streaming and cost**: SSE translation, pricing table, cost per request, budgets and rate limits in Redis.
3. **Tracing, logs and API monitoring**: OTel Collector, ClickHouse, Python and Node.js SDKs, live view, per-endpoint metrics, latency breakdown, slow queries, logs explorer.
4. **Security**: anomaly alerts, audit log, PII redaction, SSO and RBAC.
5. **LLM debugging and Claude Code analytics**: trace views, per-model metrics, prompt versions, Claude Code dashboards.
6. **Packaging**: web UI polish, Docker Compose, Helm chart, docs. *Exit: v1.0 released on GitHub.*

## 16. Open technical items

| Item | Notes |
| --- | --- |
| Provider translation layer | Converting OpenAI- and Anthropic-style requests and streams (events, tool calls, usage) between providers |
| Token counting | Estimating tokens before a call (TPM limits, guardrail size) and when a stream does not report usage |
| Backpressure and graceful shutdown | Concurrency caps per pod, 503 with Retry-After, draining streams on deploy |
| Database migrations | Alembic and a ClickHouse migration runner; expand, migrate, contract for zero-downtime upgrades |
| Encryption keys | Envelope encryption with KMS; master key rotation |
| Sizing guide | CPU, memory and disk for small, medium and large installs |
| CloudWatch error grouping | Pattern fingerprints, trace linking, Lambda timeout detection |
| Decisions pending | One organization or many per install; Apache 2.0 or MIT; supported browsers; trademark check for the name |