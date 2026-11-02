"""Traces: each request the app handles and each step inside it (database calls, outgoing HTTP,
decorated functions), batched in the background to the collector's /v1/traces.

The SDK keeps its own tracer provider and hands it to every instrumentation, rather than relying
on the process-wide one (which Python lets an app set only once), so init() after shutdown()
works and an app's own OpenTelemetry setup is left alone.
"""

import importlib
from dataclasses import dataclass, field
from typing import Protocol

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from spanport._constants import (
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    OPTIONAL_INSTRUMENTATIONS,
    OTLP_TRACES_PATH,
)


class Instrumentor(Protocol):
    """The part of an OpenTelemetry instrumentor the SDK uses."""

    def instrument(self, **kwargs: object) -> None: ...

    def uninstrument(self, **kwargs: object) -> None: ...


@dataclass
class ActiveTracing:
    """Running tracing: the provider to flush and the instrumentations to switch off."""

    provider: TracerProvider
    # Module names of the optional instrumentations that were installed and switched on.
    optional: list[str] = field(default_factory=list)
    instrumentors: list[Instrumentor] = field(default_factory=list)

    def stop(self) -> None:
        """Switch the instrumentations off, then send what is queued."""
        for instrumentor in self.instrumentors:
            instrumentor.uninstrument()
        self.provider.shutdown()


def build_trace_exporter(collector_url: str, data_key: str) -> OTLPSpanExporter:
    """Exporter that sends span batches to the collector with the data key as a bearer token.

    Args:
        collector_url: Base URL of the OTel Collector, e.g. "http://localhost:4318".
        data_key: The raw data key.
    """
    return OTLPSpanExporter(
        endpoint=collector_url.rstrip("/") + OTLP_TRACES_PATH,
        headers={AUTHORIZATION_HEADER: BEARER_PREFIX + data_key},
    )


def start_tracing(service: str, exporter: SpanExporter) -> ActiveTracing:
    """Start tracing into `exporter`, with every optional instrumentation that is installed.

    Args:
        service: Service name shown in Spanport, e.g. "hr-portal-api".
        exporter: Where span batches go; OTLP in real use, in-memory in tests.

    Returns:
        The running tracing; call stop() to flush and switch it off.
    """
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    tracing = ActiveTracing(provider=provider)
    for module_name, class_name in OPTIONAL_INSTRUMENTATIONS:
        instrumentor = load_instrumentor(module_name, class_name)
        if instrumentor is None:
            continue
        instrumentor.instrument(tracer_provider=provider)
        tracing.instrumentors.append(instrumentor)
        tracing.optional.append(module_name)
    return tracing


def load_instrumentor(module_name: str, class_name: str) -> Instrumentor | None:
    """The instrumentor if its package is installed, else None."""
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        # Not installed (or its library isn't): that instrumentation is simply off.
        return None
    instrumentor: Instrumentor = getattr(module, class_name)()
    return instrumentor
