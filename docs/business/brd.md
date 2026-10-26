# Spanport: Business Requirements Document (BRD)

| Item | Detail |
| --- | --- |
| Project | Spanport: open-source LLM gateway and observability platform |
| Document owner | Nitish Bharadwaj |
| Version | 1.0 (draft) |
| Date | 10 Oct 2026 |
| Related document | Spanport: Product Spec (functional and technical detail) |

## 1. Executive summary

Teams building AI-powered applications run LLM calls across several providers, databases and services, but they cannot answer three basic questions quickly: *why is this API slow, what is it costing, and who is spending the money?* Today the answers are spread across a provider console, an APM tool, cloud logs and spreadsheets.

Spanport puts one gateway in front of every LLM provider and one observability layer across the whole application. Every API request is traced end to end, showing time spent in code, database, external services and LLM calls, together with its cost, client IP, logs and the key that paid for it. The gateway enforces budgets, rate limits and allowed models, and lets a leaked key be revoked in seconds.

Spanport is a free, open-source, standalone project that teams self-host in their own infrastructure.

## 2. Business problem

| # | Problem | Business impact |
| --- | --- | --- |
| P1 | Slow APIs cannot be traced to a cause (DB, code, external call or LLM) | Long investigations, poor user experience, wasted engineering time |
| P2 | LLM spend cannot be attributed to a client, project, feature or developer | Agencies cannot bill clients accurately; teams cannot justify AI spend |
| P3 | No hard spending limits on LLM usage | A bug, loop or leaked key can run up large bills before anyone notices |
| P4 | Raw provider keys are shared across apps and developers | A leak forces rotating keys everywhere; abuse is found only on the invoice |
| P5 | Each provider has its own API, console and billing | Switching or falling back between providers needs code changes |
| P6 | Logs live separately from traces | Debugging means correlating timestamps by hand across tools |
| P7 | AI coding tool usage (Claude Code) is invisible | No view of adoption, cost or output per developer |
| P8 | Existing tools are either US-hosted SaaS or cover only one layer | Data-residency concerns; several tools to buy and run |

## 3. Business objectives

| ID | Objective | Measure of success |
| --- | --- | --- |
| BO-1 | Make the cause of a slow API visible in one screen | A slow request's time is broken down into code, DB, external and LLM within 10 seconds of the request finishing |
| BO-2 | Attribute every rupee of LLM spend | 100% of gateway requests tagged with client, project, key and endpoint |
| BO-3 | Prevent runaway LLM spend | Hard budgets block requests once the limit is reached; alerts fire at the configured threshold |
| BO-4 | Contain key leaks quickly | A revoked key is rejected by the gateway within 1 second; real provider keys never leave the server |
| BO-5 | Remove provider lock-in | Apps switch provider or model by configuration, with automatic fallback on provider errors |
| BO-6 | Unify logs and traces | Every log written during a request links to that request's trace |
| BO-7 | Make AI coding tool usage measurable | Prompts, tokens, cost and output visible per developer and team |
| BO-8 | Grow an open-source user base | Proposed targets, to confirm: v1.0 released on GitHub; 10 teams self-hosting within 6 months of release |

## 4. Scope

### In scope (MVP, v1.0)

1. **LLM gateway**: one OpenAI- and Anthropic-compatible API for OpenAI, Anthropic, AWS Bedrock and Google Gemini; streaming; routing, retries and fallbacks; response cache.
2. **Cost and spend control**: per-request cost, budgets per key, project or client, per-client usage reports.
3. **Security and compliance**: virtual, ingest and admin keys; instant revoke; RPM/TPM limits; anomaly alerts; audit log; SSO and RBAC; PII redaction.
4. **API performance monitoring**: live request view (time, IP, location, status, duration), per-endpoint metrics, trace waterfall, slow queries, project switcher, custom time ranges.
5. **LLM debugging and quality**: LLM traces, per-model metrics, prompt versions.
6. **AI coding tool analytics**: Claude Code usage per developer and team.
7. **Logs**: log capture from existing loggers, live tail, search, log alerts, logs linked to traces.
8. **Model catalog sync**: automatic fetching of models and versions from each provider, `latest` or pinned versions on keys.

### Out of scope (for v1.0)

- Infrastructure metrics (CPU, memory, disk): remain with CloudWatch or existing tools.
- A hosted SaaS version or any paid tier.
- Azure OpenAI and other providers beyond the four above.
- Mobile apps.

## 5. Stakeholders and users

| Stakeholder / persona | Role | What they need from Spanport |
| --- | --- | --- |
| Project owner (Nitish Bharadwaj) | Builds and maintains Spanport | Clear scope, build order, adoption |
| Platform / DevOps engineer | Runs infrastructure and incidents | Live view, latency breakdown, alerts, key control, self-hosting |
| Backend developer | Builds APIs and AI features | One-line SDK setup, trace waterfall, logs next to traces, one LLM API |
| Engineering manager / agency owner | Owns delivery and budgets | Cost per client and project, budgets, Claude Code adoption and cost |
| Account / finance team | Bills clients | Per-client usage reports for invoicing |
| Security reviewer | Approves tools handling data | Self-hosting, redaction, audit log, no plaintext secrets, SSRF protection |
| Open-source community | Users and contributors | Clear docs, easy install, permissive license |

## 6. Business requirements

Priority uses MoSCoW: **M** = must have for v1.0, **S** = should have, **C** = could have.

| ID | Requirement | Rationale | Priority | Spec module |
| --- | --- | --- | --- | --- |
| BR-01 | Provide one API that reaches OpenAI, Anthropic, Bedrock and Gemini | Remove provider lock-in (P5) | M | 1 |
| BR-02 | Fall back to another provider automatically on throttling, errors or timeouts | Keep AI features available | M | 1 |
| BR-03 | Calculate the cost of every LLM request and tag it with client, project, key, endpoint and model | Cost attribution (P2) | M | 2 |
| BR-04 | Enforce budgets per key, project or client, as alerts or hard blocks | Prevent runaway spend (P3) | M | 2 |
| BR-05 | Export per-client usage reports for invoicing | Agencies bill clients (P2) | M | 2 |
| BR-06 | Issue virtual keys that hide real provider keys, show the key only once, and can be revoked or rotated instantly | Contain leaks (P4) | M | 3 |
| BR-07 | Limit each key by allowed models, requests and tokens per minute, expiry and optional IP allowlist | Least privilege, abuse control | M | 3 |
| BR-08 | Alert on unusual spend, new IPs or countries, unusual models and error bursts | Detect abuse early (P4) | M | 3 |
| BR-09 | Keep an audit log; support SSO and role-based access | Accountability, security review | S | 3 |
| BR-10 | Leave prompt and response logging off by default and redact PII when enabled | Data protection, DPDP alignment | M | 3 |
| BR-11 | Show incoming requests live with time, status, path, client IP, location, size and duration | Real-time visibility (P1) | M | 4 |
| BR-12 | Break each request's time into code, DB, service, external and LLM | Find the cause of slowness (P1) | M | 4 |
| BR-13 | Show per-endpoint request count, error rate and p50/p95/p99 latency over any time range, including custom absolute ranges | Trend and incident analysis | M | 4 |
| BR-14 | Flag slow queries and N+1 patterns | Common root cause of slow APIs | S | 4 |
| BR-15 | Scope every view by client, project and environment | Multi-client teams | M | 4 |
| BR-15a | Show times in UTC by default and let each user switch to any timezone, per screen or as a saved default; store all data in UTC | Teams across countries; avoid timezone mistakes during incidents | M | 4 |
| BR-16 | Show LLM latency, time to first token, tokens and errors per model, and compare prompt versions | Choose and tune models | S | 5 |
| BR-17 | Report Claude Code usage per developer and team: prompts, tokens, cost, lines changed, commits, PRs | Measure AI coding tool value (P7) | S | 6 |
| BR-18 | Capture logs from existing loggers without code changes and link each log to its request's trace | Unify logs and traces (P6) | M | 7 |
| BR-19 | Search logs with an EC2-style filter bar (property, operator, value chips joined by and / or), plus an optional text query with AND, OR, NOT, exact phrases, field filters, wildcards and brackets; tail them live, view past ranges within the 7-day retention window and alert on log patterns | Debugging and incident response | M | 7 |
| BR-19a | Export the results of any log search as CSV or JSON lines, respecting filters, time range and project; large exports (up to 10 million lines, CSV split into 1,000,000-row files) delivered by emailed link; 100,000 lines download in under 15 seconds; every export audited | Share and analyse log evidence outside Spanport | M | 7 |
| BR-20 | Fetch available models and versions from each provider automatically; let keys use `latest` or pin a version | Keep model lists current without manual work | M | Model catalog sync |
| BR-21 | Flag models with no price so cost tracking is never silently wrong | Accurate budgets | M | Model catalog sync |
| BR-22 | Run every component as a container: one command (`docker compose up`) starts the full platform; the Helm chart uses the same images | Data residency, no SaaS dependency (P8) | M | Packaging |
| BR-27 | Record deploys from CI and show them on API charts | Tie slowdowns to releases | M | Production readiness |
| BR-28 | Sample traces per project, always keeping errors and slow requests | Control storage cost at high volume | M | Production readiness |
| BR-29 | Enforce a daily data limit per project without blocking apps | Stop one project from affecting others | M | Production readiness |
| BR-30 | Enforce organization and project isolation in the database, with tests | Multi-client safety | M | Production readiness |
| BR-31 | Back up configuration and telemetry nightly with a documented restore | Recover from failure | M | Production readiness |
| BR-32 | Expose health and Prometheus metrics for every component | Spanport notices its own problems | M | Production readiness |
| BR-33 | Scan dependencies and images, sign images, publish an SBOM per release | Trustworthy open-source releases | M | Production readiness |
| BR-34 | Simple UI: Home answering broken / slow / spend, grouped navigation, plain-language labels | Usable by non-experts | M | UI |
| BR-35 | Group identical errors with counts, affected users, first / last seen and release; assign, resolve, ignore | Developers fix problems, not read raw logs | M | Errors |
| BR-36 | Track alert states (firing, acknowledged, resolved) and keep alert history | Know who is handling what | M | Alerts |
| BR-37 | Send alerts to Microsoft Teams, PagerDuty and Opsgenie as well as email, Slack and webhook | Fit existing on-call tools | M | Alerts |
| BR-38 | Hide or block personal data and prompt injection in prompts before they reach providers | Data protection and safety | M | Guardrails |
| BR-39 | Publish a stable public API with interactive docs and an OpenAPI spec | Automation without the UI | M | API |
| BR-40 | Document versioning, SDK compatibility, upgrades and rollback | Safe upgrades | M | Operations |
| BR-41 | Find and delete one person's data across Spanport on request, with an audit record | DPDP / GDPR compliance | M | Privacy |
| BR-42 | Offer sample data at setup with one-click removal | Fast first impression | M | Onboarding |
| BR-43 | Monitor web apps with a browser SDK and browser keys: page speed, JavaScript errors, links to backend requests | See the user’s real experience end to end | M | Web app |
| BR-44 | Draw a service map from traces with health per service and link | Understand dependencies at a glance | M | Service map |
| BR-45 | Accept, chart and alert on custom app metrics (OpenTelemetry) | Track business numbers next to performance | M | Metrics |
| BR-46 | Collect user feedback and grade a sample of LLM answers automatically, compared per prompt version | Know whether answers are good, not only fast and cheap | M | Quality |
| BR-47 | Load-balance across deployments, route simple prompts to cheaper models with a quality guard, and offer a semantic cache | Lower cost and higher availability | M | Routing |
| BR-48 | Forecast month-end spend and estimate savings | Avoid budget surprises | M | Costs |
| BR-49 | Budgets per model and per end user on LLM keys | Stop one model or one user from using the whole budget | M | Keys |
| BR-50 | Use only strictly necessary cookies (session, CSRF, sign-in, optional trusted browser) with HttpOnly, Secure, SameSite and the __Host- prefix; revocable sessions; no keys or tokens in browser storage | Account security without a consent banner | M | Security |
| BR-51 | Rate-limit the gateway, API, sign-in and ingest with clear 429 responses and Retry-After; never block apps sending data | Fair use, protection from abuse and runaway scripts | M | Platform |
| BR-52 | Cursor-paginate every list with a single response shape, fast at any depth | Large data stays usable | M | Platform |
| BR-53 | Load screens, heavy libraries and details only when needed; infinite scroll with virtualization for long lists | Fast first load and smooth screens | M | UI |
| BR-54 | Cache safely: separate state and cache Redis; protect against stampedes, mass expiry, missing-key floods and stale data; instant invalidation on changes; monitor hit ratio and evictions | Fast under load without wrong answers or outages | M | Platform |
| BR-55 | Let owners see Redis and ClickHouse storage and delete unneeded cache keys, groups or project data safely: previews, typed confirmation, no deletion of budgets, audit records | Free space and fix problems without risking data | M | Operations |
| BR-56 | Protect every outgoing request to an address a user typed (webhook, Microsoft Teams, Loki, Elasticsearch, Kafka, SMTP) from reaching private networks or cloud metadata (SSRF): https only on allowed ports; no credentials in URLs; block private, loopback, link-local, carrier-grade NAT and metadata addresses including IPv6 and IPv4-mapped forms; check when saved and again at send time, connecting to the checked address; no redirects; short timeouts and a 64 KB response limit; never show response bodies; validate before writing collector configuration | Stop attackers using Spanport to reach internal systems or AWS credentials | M | Security |
| BR-57 | Run the read-only SQL box as a restricted ClickHouse user that cannot use url, s3, remote, file or similar table functions (`remote_url_allow_hosts` empty), limited by row policies to its own organization and projects | ClickHouse cannot be used to fetch internal addresses or other tenants' data | M | Security |
| BR-58 | Defend outgoing traffic at the network level: IMDSv2 with hop limit 1 and IAM roles for service accounts on AWS; egress rules allowing the server, collector and job workers to reach the internet and their own databases only; PDF reports rendered with network access off; prompt image URLs fetched only through the same URL guard | One application bug is not enough for an SSRF attack to succeed | M | Security |
| BR-59 | Let administrators restrict outgoing destinations to an allow-list of domains (for example hooks.slack.com, *.webhook.office.com, *.yourco.com) | Tighter control for regulated installs | S | Security |
| BR-60 | Sign every outgoing webhook with HMAC-SHA256 and a timestamp, and document how receivers verify it | Receivers can trust Spanport alerts and reject replays | M | Security |
| BR-61 | Show storage settings and health on the Storage screen: retention per ClickHouse table (logs at most 7 days), Redis memory limits for state and cache, ClickHouse disk use with alerts at 80%, redis-state memory with alerts at 70%, evictions on redis-state with an alert on any eviction | Space problems are visible and acted on before they cause outages | M | Operations |
| BR-62 | Serve everything through one HTTPS front door (Caddy) with automatic certificates, HTTP→HTTPS redirect, security headers and routing; only ports 80 and 443 public | Secure sign-in and encrypted traffic with no manual certificate work | M | Security |
| BR-63 | Stop the provider's generation when the calling app disconnects, record only the tokens produced, show the savings, and document how apps pass the cancel signal | Do not pay for answers nobody reads | M | Gateway |
| BR-64 | Protect against slow or failing providers with connect and first-token timeouts, per-deployment circuit breakers, a retry budget and connection pools, all visible and adjustable on the Providers screen | AI features stay up when a provider has problems | M | Gateway |
| BR-65 | Run each scheduled job exactly once across all server pods, retry failures 3 times, then hold them for a person; show schedules, last and next runs, and Run now | No duplicate backups, emails or syncs; failures are not silent | M | Operations |
| BR-66 | Organize the code in the agreed folder structure: layered backend apps, shared `packages/core`, feature folders in the UI | New contributors find things quickly | M | Engineering |
| BR-67 | Keep business logic out of UI components and controllers (hooks, pure functions and services instead), checked automatically | Logic is testable and screens stay simple | M | Engineering |
| BR-68 | Fail the build on dead code, unused dependencies and copy-paste duplication | The codebase stays small and clean | M | Engineering |
| BR-69 | Follow one naming convention for files, code, API paths, JSON, database, Redis keys, environment variables and commits | Consistency across the project | M | Engineering |
| BR-70 | Handle errors everywhere with one API error format (RFC 9457 + codes + request ID), no swallowed errors, timeouts on outside calls, and designed error states on every screen | Clear failures for users and operators | M | Engineering |
| BR-71 | Keep all environment configuration and secrets out of code: typed settings validated at start-up, `.env.example` only, secrets manager, runtime config for the browser | Safe, portable deployments | M | Engineering |
| BR-72 | Build screens from a shared component kit and shared backend helpers | Consistent UI and less code | M | Engineering |
| BR-73 | Manage state by type: server data in TanStack Query, view state in the URL, a small global store, typed forms | Predictable behavior, shareable views | M | Engineering |
| BR-74 | Document the codebase: READMEs, docstrings and TSDoc, ADRs, generated OpenAPI with examples, changelog, runbooks | Easier contribution and operation | M | Engineering |
| BR-75 | Structure the API for growth: versioning, a router per domain, separate schemas, resource routes, cursor pagination, auth, rate limits, idempotency, async jobs, request IDs | The API scales with features and users | M | Engineering |
| BR-76 | Show AI coding tool cost per project and per member (Claude Code in the terminal and VS Code), with project members, a coding budget per project, and an "Unassigned" bucket; match sessions by repo tag, project key or Git-remote rule | Know what each client project costs in AI-assisted development and who used it | M | Claude Code analytics |
| BR-77 | Summarize what each project used the coding assistant for (topics) without showing prompt text | Useful insight without reading people's prompts | S | Claude Code analytics |
| BR-78 | Allow optional, per-project recording of coding prompts only after the team is told in writing; members see a notice; Owner/Admin access only; secrets and personal data hidden; every view audited; deleted after 7–30 days | Investigation when needed, while respecting privacy law and team trust | S | Claude Code analytics, Privacy |
| BR-79 | Let apps send logs without writing any sending code: the SDK captures normal logging after two lines at start-up; other languages need no code change (the collector reads stdout or log files); downloads and archives use NDJSON | Getting logs in is effortless and cannot break the app | M | Logs |
| BR-80 | Follow the visual design rules: dark graphite theme with one teal accent, no white surfaces or purple, six type sizes and eight spacing steps from design tokens, golden-ratio main and side panels, small-corner (not pill) buttons, specific labels, no emoji, no em dashes, no scroll or decorative animations | The product looks deliberate and trustworthy, not generated | M | UI |
| BR-81 | Show 4xx and 5xx errors over time and let users select any moment to see the exact failing requests, by status code and API, with links to their traces and logs | Find what failed at a given time in two clicks | M | Monitoring |
| BR-82 | Keep navigation small: 16 sidebar items at most, related views as tabs on one page, pages that only some projects use shown only when used, one-time screens as Home cards | Users find things quickly as features grow | M | UI |
| BR-24 | Forward copies of a project's logs to CloudWatch Logs, Grafana Loki, Elasticsearch/OpenSearch, Amazon S3 or Kafka, with level filters, connection tests and status | Long-term retention beyond 7 days; reuse existing dashboards | M | Integrations |
| BR-25 | Pull logs in from CloudWatch log groups, Kafka and OTLP shippers (Alloy, Fluent Bit, Vector, Logstash) | Bring existing logs under Spanport search and alerts | M | Integrations |
| BR-26 | Search CloudWatch, Loki and Elasticsearch in place from the Logs screen using the same filters | Avoid copying large existing log stores | M | Integrations |
| BR-23 | Provide dashboards, a read-only SQL box and alerts by email, Slack or webhook | Self-serve analysis | S | Shared |

## 7. Non-functional and business constraints

| Area | Requirement |
| --- | --- |
| Performance | Gateway adds under 15 ms p95 latency; data visible in the UI within 10 seconds |
| Availability | Gateway 99.9%; an observability outage never blocks LLM traffic |
| Data residency | All data stays in the user's own infrastructure; India region supported |
| Security | TLS everywhere; secrets encrypted at rest; tenant isolation on every query; only strictly necessary, HttpOnly / Secure / SameSite cookies; every outgoing request to a user-entered address passes the SSRF guard |
| Storage | Owner-only Storage screen; cache deletable, important data (budgets, limits, sessions) protected; ClickHouse deletions previewed, confirmed and audited |
| Code quality | Engineering rules in `docs/engineering/rules.md` apply to every change; CI enforces layering, dead code, duplication, naming, secrets and the API spec |
| Retention | Logs 7 days maximum; traces 30 days and metrics 13 months by default, configurable |
| Cost to users | Free and open source; users pay only for their own infrastructure |
| Packaging | Container-first: every component ships as a container image; one command starts everything |
| Technology | Python for the gateway, backend and Python SDK; TypeScript for the Node.js SDK and web UI; OpenTelemetry; ClickHouse, PostgreSQL, Redis |

## 8. Assumptions

- Users can run containers (Docker or Kubernetes) and have access to their LLM provider credentials.
- Provider model-list APIs remain available; prices are maintained in Spanport's pricing file because providers do not expose them through those APIs.
- Applications can add the Spanport SDK (Python or Node.js), or can at least route LLM calls through the gateway. Apps in other languages use their own OpenTelemetry SDK pointed at Spanport's OTLP endpoint.
- OpenTelemetry semantic conventions remain stable enough to classify spans.

## 9. Dependencies

- LLM provider APIs: OpenAI, Anthropic, AWS Bedrock, Google Gemini.
- OpenTelemetry SDKs, instrumentation libraries and Collector.
- ClickHouse, PostgreSQL, Redis.
- Claude Code's OpenTelemetry telemetry for coding tool analytics.

## 10. Constraints

- Built as a standalone project by a small team (initially one person).
- No revenue model: the project must be cheap to maintain (docs site and CI only).
- The owner should confirm that their employment agreement permits a standalone open-source project before public release.

## 11. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Crowded market (LiteLLM, Langfuse, SigNoz, CloudWatch) | Low adoption | Lead with unique value: per-endpoint latency and cost in one trace, enforcement, per-client attribution |
| Scope of a seven-module MVP for a small team | Delayed release | Build in the defined order and release each step publicly |
| Provider API changes (streaming formats, model IDs) | Broken adapters | Contract tests per provider; normalization rules file |
| Storing prompts and logs | Data liability | Logging off by default, redaction, short retention, self-hosting |
| Gateway as a single point of failure | Outage for AI features | Stateless pods, multi-AZ, fail-open on tracing |
| SSRF through webhooks, integrations, the SQL box or PDF rendering | Access to internal systems or cloud credentials | URL guard checked at save and send time, restricted ClickHouse user, offline PDF rendering, IMDSv2 and egress rules (BR-56 to BR-59) |
| Wrong data deleted from Storage | Lost logs or reset budgets | Owner only, budgets and limits not deletable, preview and typed confirmation, audit log, nightly backups (BR-55, BR-61) |

## 12. Milestones

Dates to be set by the project owner.

| # | Milestone | Done when |
| --- | --- | --- |
| M1 | Gateway core | Internal apps call OpenAI, Anthropic, Bedrock and Gemini through virtual keys; model catalog syncs |
| M2 | Streaming and cost | Per-request cost recorded; budgets and rate limits enforced |
| M3 | Tracing, logs and API monitoring | A slow API is diagnosed to DB vs code vs LLM from the live view and trace; logs linked |
| M4 | Security | Anomaly alerts, audit log, PII redaction, SSO and RBAC working |
| M5 | LLM debugging and Claude Code analytics | Per-model metrics and Claude Code dashboards populated |
| M6 | v1.0 release | Docker Compose and Helm installs documented; release published on GitHub |

## 13. Success metrics (KPIs)

| KPI | Target |
| --- | --- |
| Time to find the cause of a slow API | Under 5 minutes from opening Spanport |
| Gateway requests with full cost attribution | 100% |
| Budget overruns on hard-limited keys | 0 |
| Time to block a leaked key | Under 1 minute end to end |
| Logs correlated to a trace (for requests with the SDK) | Over 95% |
| Teams self-hosting after release | Proposed: 10 within 6 months |

## 14. Open questions

- License: Apache 2.0 or MIT.
- Trademark, domain, GitHub, PyPI and npm availability for "Spanport".
- Final adoption targets for BO-8.

## 15. Approval

| Name | Role | Decision | Date |
| --- | --- | --- | --- |
| Nitish Bharadwaj | Project owner | | |
| | Reviewer | | |