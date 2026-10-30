import time

import pytest
from fakes import SAMPLE_DATA_KEY, FakeApiKeyStore, FakeLogWriter
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from otlp_samples import make_record, make_request

from spanport_server.core.errors import InvalidRequestError, StorageUnavailableError
from spanport_server.services.log_ingest_service import LogIngestService

pytestmark = pytest.mark.anyio


async def test_stores_every_record_under_the_keys_project() -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    writer = FakeLogWriter()
    payload = make_request(make_record("a"), make_record("b")).SerializeToString()

    stored = await LogIngestService(writer).ingest(key, payload)

    assert stored == 2
    assert {(row.org_id, row.project_id) for row in writer.rows} == {(key.org_id, key.project_id)}


async def test_logs_older_than_retention_are_dropped_and_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    writer = FakeLogWriter()
    eight_days_ago = time.time_ns() - 8 * 24 * 3600 * 1_000_000_000
    payload = make_request(
        make_record("fresh"), make_record("expired", time_unix_nano=eight_days_ago)
    ).SerializeToString()

    stored = await LogIngestService(writer).ingest(key, payload)

    assert stored == 1
    assert [row.message for row in writer.rows] == ["fresh"]
    assert "records=1 dropped_expired=1" in caplog.text


async def test_an_empty_request_writes_nothing() -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    writer = FakeLogWriter(storage_down=True)

    stored = await LogIngestService(writer).ingest(
        key, ExportLogsServiceRequest().SerializeToString()
    )

    assert stored == 0


async def test_invalid_payload_is_rejected() -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)

    with pytest.raises(InvalidRequestError):
        await LogIngestService(FakeLogWriter()).ingest(key, b"\xff\xff not protobuf")


async def test_storage_outage_reaches_the_caller() -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    payload = make_request(make_record()).SerializeToString()

    with pytest.raises(StorageUnavailableError):
        await LogIngestService(FakeLogWriter(storage_down=True)).ingest(key, payload)


async def test_logs_one_line_without_the_message_text(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    payload = make_request(make_record("secret customer note")).SerializeToString()

    await LogIngestService(FakeLogWriter()).ingest(key, payload)

    assert len(caplog.records) == 1
    assert "logs ingested" in caplog.text
    assert "records=1" in caplog.text
    assert "secret customer note" not in caplog.text
