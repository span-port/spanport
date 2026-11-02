"""Your own steps in a trace: `span("name")` for any block, and the `@trace()` decorator for a
function or for every method of a class (e.g. a service), named "ClassName.method".
"""

import functools
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Span, Tracer

from spanport._constants import SDK_SCOPE_NAME, SPAN_NAME_SEPARATOR

Decorated = TypeVar("Decorated")

# Set while the SDK is running; steps are recorded into its own tracer provider.
_tracer: Tracer | None = None


def use_tracer_provider(provider: otel_trace.TracerProvider | None) -> None:
    """Record steps into `provider` (the SDK's own), or nowhere (None) after shutdown."""
    global _tracer
    _tracer = None if provider is None else provider.get_tracer(SDK_SCOPE_NAME)


def _current_tracer() -> Tracer:
    """The SDK's tracer, or the no-op one when the SDK isn't running (steps are then free)."""
    return _tracer or otel_trace.NoOpTracer()


@contextmanager
def span(name: str) -> Iterator[Span]:
    """A step of the trace, nested under the current one. An exception marks it failed and is
    re-raised unchanged.

        with spanport.span("build prompt"):
            ...
    """
    # OpenTelemetry records the exception and sets the error status itself, then re-raises.
    with _current_tracer().start_as_current_span(name) as current:
        yield current


def trace(name: str | None = None) -> Callable[[Decorated], Decorated]:
    """Decorator: time a function, or every method of a class, as a step of the trace.

        @spanport.trace()
        class VariablesService:
            async def list(self, environment_id: str) -> list[Variable]: ...

    Sync and async functions both work. Steps are named after the function, or
    "ClassName.method" for a class.

    Args:
        name: The span name (function) or the name before the dot (class); defaults to its own.
    """

    def decorate(target: Decorated) -> Decorated:
        if inspect.isclass(target):
            _trace_class(target, name or target.__name__)
            return target
        if inspect.isfunction(target):
            return _timed(target, name or target.__qualname__)  # type: ignore[return-value]
        return target

    return decorate


def _trace_class(cls: type, class_name: str) -> None:
    """Replace each method defined on the class with a timed one."""
    for attribute, value in list(vars(cls).items()):
        if attribute.startswith("__") or not inspect.isfunction(value):
            continue
        setattr(cls, attribute, _timed(value, f"{class_name}{SPAN_NAME_SEPARATOR}{attribute}"))


def _timed(function: Callable[..., Any], span_name: str) -> Callable[..., Any]:
    """The function, run inside a span; async functions are awaited inside it."""
    if inspect.iscoroutinefunction(function):

        @functools.wraps(function)
        async def timed_async(*args: Any, **kwargs: Any) -> Any:
            with span(span_name):
                return await function(*args, **kwargs)

        return timed_async

    @functools.wraps(function)
    def timed(*args: Any, **kwargs: Any) -> Any:
        with span(span_name):
            return function(*args, **kwargs)

    return timed
