# Spanport

**Open-source, self-hosted LLM gateway and observability platform.** One trace answers: "this API took 4.2 s: 0.2 s in the database, 0.4 s in our code, 3.6 s in the Claude call, 2,300 tokens, ₹1.80."

Spanport sits between your apps and LLM providers (OpenAI, Anthropic, AWS Bedrock, Google Gemini), and collects your apps' requests, logs and errors, so cost, speed and failures are visible in one place. Everything runs in your own infrastructure. Free, no paid tier.

> **Status:** design complete for v1.0 (product, technical and business requirements, UI for every screen, database schema). Implementation is in progress, following the build order in the TRD. Working and tested today: model catalog API, rate limiting, cursor pagination, caching helpers, storage administration, the database schemas, and the Docker Compose setup.

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

Until Caddy is added to the Compose file (the next build step), the services are reached directly: UI at http://localhost:3000, API docs at http://localhost:3000/api/docs, gateway at http://localhost:4000.

Containers: `caddy`, `ui`, `server`, `gateway`, `collector`, `postgres`, `clickhouse`, `redis-state` (budgets, limits, sessions; never evicted), `redis-cache` (caches; least-recently-used eviction). For large installs, add Kafka with `make up-kafka`.

Commands: `make ps` (status and health) · `make logs` · `make down` (keeps data) · `make reset` (deletes data) · `make test`.

On Kubernetes, the Helm chart in `deploy/helm/spanport` runs the same images.

## Connect an app

**Send requests, logs and errors** (Python):

```python
pip install spanport

import spanport
spanport.init(data_key="sp_ingest_…", service="hr-portal-api")
# keep logging as usual; requests, database calls and logs are captured
```

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