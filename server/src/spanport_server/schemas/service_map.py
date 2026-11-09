"""The service map: what calls what in a project (your services, databases, outgoing calls and
LLM providers), drawn from stored spans.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict

from spanport_server.core.ids import UuidV7


class MapStatus(StrEnum):
    """How a box or line looks: fine, slower than the period before, or failing too often."""

    OK = "ok"
    SLOW = "slow"
    BAD = "bad"


class ServiceMapRequest(BaseModel):
    """One project's map over a time range (at most 30 days back)."""

    model_config = ConfigDict(extra="forbid")

    project_id: UuidV7
    start: AwareDatetime
    end: AwareDatetime


class MapNode(BaseModel):
    """One box: a service of yours (`service`), a database (`db`), another system it calls
    (`external`) or an LLM provider (`llm`). Calls are the requests it answered (a service) or
    the calls made to it (anything else).
    """

    id: str
    kind: str
    name: str
    calls: int
    errors: int
    p50_ms: float
    p95_ms: float
    status: MapStatus
    calls_to: list[str]
    called_by: list[str]


class MapEdge(BaseModel):
    """One line: calls from `source` to `target` (node ids) over the range."""

    source: str
    target: str
    calls: int
    errors: int
    p50_ms: float
    p95_ms: float
    status: MapStatus


class ServiceMapResponse(BaseModel):
    """The boxes and lines. `range_seconds` turns calls into rates."""

    range_seconds: float
    nodes: list[MapNode]
    edges: list[MapEdge]


@dataclass(frozen=True)
class CallStats:
    """Calls, failures and the typical and slow-5% times, in nanoseconds."""

    calls: int
    errors: int
    p50_ns: float
    p95_ns: float


@dataclass(frozen=True)
class ServiceRow:
    """One service's incoming requests."""

    service: str
    stats: CallStats


@dataclass(frozen=True)
class StepEdgeRow:
    """A service's calls to a database, another system or an LLM provider (`target`), by
    span category.
    """

    service: str
    category: str
    target: str
    stats: CallStats


@dataclass(frozen=True)
class ServiceEdgeRow:
    """Requests one of your services (`caller`) made to another (`callee`)."""

    caller: str
    callee: str
    stats: CallStats


@dataclass(frozen=True)
class MapRows:
    """Everything the map is drawn from, for one period."""

    services: list[ServiceRow]
    steps: list[StepEdgeRow]
    service_calls: list[ServiceEdgeRow]
