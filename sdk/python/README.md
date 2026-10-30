# spanport (Python SDK)

Send your Python app's logs to Spanport. Keep logging the way you already do.

```bash
pip install spanport
```

```python
import logging
import spanport

spanport.init(
    # From: python -m spanport_server.cli create-data-key
    data_key="sp_ingest_...",
    service="hr-portal-api",
    # Defaults: http://localhost:4318 and http://localhost:8000
    collector_url="https://spanport-collector.example.com",
    server_url="https://spanport.example.com",
)

logging.getLogger(__name__).error("Payment failed for order 1042")
```

- **Every `logging` call is sent**, at the level your app already logs at (the root logger's level).
- **Logs are sent in the background**, in batches every few seconds. `spanport.shutdown()` sends what is left; it also runs on normal exit.
- **Logs inside an OpenTelemetry span** carry that span's `trace_id` and `span_id`, so they show up with the request.
- **Wrong key?** At start-up the SDK asks the server once whether the key is valid and prints a clear error on stderr if not. Pass `check_key=False` if the app cannot reach the server.
- **Use `https://` for anything beyond your own machine or Docker network.** The data key is sent with every batch; over plain `http://` it travels unencrypted.
- **It never breaks your app.** `init()` never raises; problems are printed on stderr as `spanport: ...` and the app carries on.

Python 3.12 or newer.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
```
