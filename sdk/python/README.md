# spanport (Python SDK)

Send your Python app's logs, and where each request spends its time, to Spanport. Keep logging the way you already do.

```bash
pip install "spanport[fastapi,sqlalchemy,httpx]"   # or spanport[all]; plain spanport for logs only
```

```python
import logging
import spanport

spanport.init(
    # From Setup → API keys → Data keys in Spanport (shown once)
    data_key="sp_ingest_...",
    service="hr-portal-api",
    # Default: http://localhost:4318
    collector_url="https://spanport-collector.example.com",
    # Your Spanport address (the UI's URL; it forwards /api to the server)
    server_url="https://spanport.example.com",
)

logging.getLogger(__name__).error("Payment failed for order 1042")
```

- **Every `logging` call is sent**, at the level your app already logs at (the root logger's level).
- **Logs are sent in the background**, in batches every few seconds. `spanport.shutdown()` sends what is left; it also runs on normal exit.
- **Logs inside an OpenTelemetry span** carry that span's `trace_id` and `span_id`, so they show up with the request.
- **Wrong key?** At start-up the SDK asks `server_url` once whether the key is valid and prints a clear error on stderr if not. Set `server_url` to your Spanport address (the UI's URL, since it forwards `/api` to the server). Without it, the check goes to `http://localhost:8000` only when the collector is on localhost too; with a collector elsewhere the check is skipped (with a note on stderr), so the key is never sent to whatever happens to answer on your own machine. Pass `check_key=False` if the app cannot reach the server.
- **Use `https://` for anything beyond your own machine or Docker network.** The data key is sent with every batch; over plain `http://` it travels unencrypted, and the SDK warns once on stderr when the collector or server is a plain `http://` address on another machine.
- **It never breaks your app.** `init()` never raises; problems are printed on stderr as `spanport: ...` and the app carries on.

Python 3.12 or newer.

## Request timing (traces)

`init()` also times each request your app handles and every step inside it, and sends them as traces; open **Requests** in Spanport to see them as a waterfall (request → your code → database / outgoing calls). Pass `traces=False` to send logs only.

**Libraries**: install the extra for each one you use, and `init()` times it automatically:

| Extra | Times |
| --- | --- |
| `spanport[fastapi]`, `[flask]`, `[django]` | each incoming request, with its route |
| `spanport[sqlalchemy]`, `[psycopg]` | each database query |
| `spanport[httpx]`, `[requests]` | each outgoing HTTP call (and passes the trace on, so your other services join it) |

Call `spanport.init()` **before** the web app is created (`app = FastAPI()`), so its requests are timed. On start-up the SDK says which libraries it found: `spanport: also timing: opentelemetry.instrumentation.fastapi, ...`.

**Your own code**: time a service or controller, or any block:

```python
@spanport.trace()                      # every method: "VariablesService.list", ...
class VariablesService:
    async def list(self, environment_id: str) -> list[Variable]: ...

@spanport.trace()                      # one function
def score_resume(text: str) -> float: ...

with spanport.span("build prompt"):    # any block
    prompt = render(template, data)
```

Async functions work the same. An exception marks the step failed and is re-raised unchanged. Logs written during a step carry its trace, so **See logs** on a request in Spanport shows them.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
```
