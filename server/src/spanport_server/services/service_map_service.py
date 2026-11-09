"""The service map: what calls what in a project over a time range, with how often, how fast
and how often it fails. A line or box is red when too many calls fail and orange when its
slow-5% time is much higher than in the period of the same length just before.

Same rules as the APIs screen: own org, projects the caller may see, a range within 30 days.
"""

import logging
import time
from dataclasses import dataclass, field, replace
from typing import Protocol

from spanport_server.core.constants import (
    MAP_ERROR_SHARE,
    MAP_ID_SEPARATOR,
    MAP_KIND_SERVICE,
    MAP_SLOWER_TIMES,
    MAX_MAP_EDGES,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import EndpointQuery
from spanport_server.schemas.service_map import (
    CallStats,
    MapEdge,
    MapNode,
    MapRows,
    MapStatus,
    ServiceMapRequest,
    ServiceMapResponse,
)
from spanport_server.services.endpoint_detail_service import step_kind
from spanport_server.services.endpoint_service import as_ms
from spanport_server.services.log_search_service import ProjectLookup
from spanport_server.services.trace_service import check_visible_project, span_range

logger = logging.getLogger(__name__)


class ServiceMapStore(Protocol):
    """Stored spans, read as what calls what."""

    async def map_rows(self, query: EndpointQuery, limit: int) -> MapRows:
        """Each service's requests and its calls, for one period."""
        ...


@dataclass(frozen=True)
class Line:
    """A line between two node ids, with its calls in this and the period before."""

    source: str
    target: str
    stats: CallStats
    previous_p95_ns: float | None


@dataclass
class NodeTotals:
    """A box's calls added up from its lines (or its own requests, for a service)."""

    kind: str
    name: str
    calls: int = 0
    errors: int = 0
    # Typical time weighted by calls; slow-5% time is the slowest line's.
    weighted_p50_ns: float = 0.0
    p95_ns: float = 0.0
    status: MapStatus = MapStatus.OK
    calls_to: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)


def node_id(kind: str, name: str) -> str:
    """A node's id, e.g. "service:kosha-backend" or "db:postgresql · kosha"."""
    return f"{kind}{MAP_ID_SEPARATOR}{name}"


def map_status(stats: CallStats, previous_p95_ns: float | None) -> MapStatus:
    """Red above MAP_ERROR_SHARE failed calls, orange at MAP_SLOWER_TIMES the slow-5% time of
    the period before, else fine.
    """
    if stats.calls and stats.errors / stats.calls > MAP_ERROR_SHARE:
        return MapStatus.BAD
    if previous_p95_ns and stats.p95_ns >= MAP_SLOWER_TIMES * previous_p95_ns:
        return MapStatus.SLOW
    return MapStatus.OK


def worse(left: MapStatus, right: MapStatus) -> MapStatus:
    """The more alarming of two statuses."""
    order = [MapStatus.OK, MapStatus.SLOW, MapStatus.BAD]
    return max(left, right, key=order.index)


def lines_of(rows: MapRows) -> dict[tuple[str, str], CallStats]:
    """Every line of a period, by (source id, target id)."""
    lines = {
        (node_id(MAP_KIND_SERVICE, row.service), node_id(step_kind(row.category), row.target)): (
            row.stats
        )
        for row in rows.steps
    }
    for row in rows.service_calls:
        source = node_id(MAP_KIND_SERVICE, row.caller)
        lines[(source, node_id(MAP_KIND_SERVICE, row.callee))] = row.stats
    return lines


def build_map(rows: MapRows, previous: MapRows, range_seconds: float) -> ServiceMapResponse:
    """The boxes and lines of one period, coloured against the period before."""
    previous_services = {row.service: row.stats.p95_ns for row in previous.services}
    previous_lines = lines_of(previous)
    nodes: dict[str, NodeTotals] = {}
    for row in rows.services:
        totals = nodes.setdefault(
            node_id(MAP_KIND_SERVICE, row.service), NodeTotals(MAP_KIND_SERVICE, row.service)
        )
        totals.calls, totals.errors = row.stats.calls, row.stats.errors
        totals.weighted_p50_ns = row.stats.p50_ns * row.stats.calls
        totals.p95_ns = row.stats.p95_ns
        totals.status = map_status(row.stats, previous_services.get(row.service))
    lines: list[Line] = []
    for (source, target), stats in lines_of(rows).items():
        before = previous_lines.get((source, target))
        lines.append(Line(source, target, stats, before.p95_ns if before else None))
        add_line(nodes, lines[-1])
    edges = [
        MapEdge(
            source=line.source,
            target=line.target,
            calls=line.stats.calls,
            errors=line.stats.errors,
            p50_ms=as_ms(line.stats.p50_ns),
            p95_ms=as_ms(line.stats.p95_ns),
            status=map_status(line.stats, line.previous_p95_ns),
        )
        for line in lines
    ]
    return ServiceMapResponse(
        range_seconds=range_seconds,
        nodes=[map_node(identifier, totals) for identifier, totals in nodes.items()],
        edges=edges,
    )


def add_line(nodes: dict[str, NodeTotals], line: Line) -> None:
    """Join a line to its two boxes. A box that isn't a service of yours adds up its lines."""
    source_kind, _, source_name = line.source.partition(MAP_ID_SEPARATOR)
    target_kind, _, target_name = line.target.partition(MAP_ID_SEPARATOR)
    source = nodes.setdefault(line.source, NodeTotals(source_kind, source_name))
    target = nodes.setdefault(line.target, NodeTotals(target_kind, target_name))
    source.calls_to.append(target_name)
    target.called_by.append(source_name)
    if target_kind == MAP_KIND_SERVICE:
        return
    target.calls += line.stats.calls
    target.errors += line.stats.errors
    target.weighted_p50_ns += line.stats.p50_ns * line.stats.calls
    target.p95_ns = max(target.p95_ns, line.stats.p95_ns)
    target.status = worse(target.status, map_status(line.stats, line.previous_p95_ns))


def map_node(identifier: str, totals: NodeTotals) -> MapNode:
    """A box in milliseconds."""
    return MapNode(
        id=identifier,
        kind=totals.kind,
        name=totals.name,
        calls=totals.calls,
        errors=totals.errors,
        p50_ms=as_ms(totals.weighted_p50_ns / totals.calls) if totals.calls else 0.0,
        p95_ms=as_ms(totals.p95_ns),
        status=totals.status,
        calls_to=sorted(totals.calls_to),
        called_by=sorted(totals.called_by),
    )


class ServiceMapService:
    """Builds the service map from stored spans."""

    def __init__(self, projects: ProjectLookup, spans: ServiceMapStore) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            spans: Stored spans (ClickHouse).
        """
        self._projects = projects
        self._spans = spans

    async def service_map(self, caller: Caller, request: ServiceMapRequest) -> ServiceMapResponse:
        """What calls what over the range, coloured against the period just before it.

        Raises:
            NotFoundError: The project isn't in the caller's org or not visible to them.
            InvalidRequestError: Bad range (backwards or older than 30 days).
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        await check_visible_project(caller, request.project_id, self._projects)
        start, end = span_range(request.start, request.end)
        query = EndpointQuery(
            org_id=caller.org_id, project_id=request.project_id, start=start, end=end, service=""
        )
        rows = await self._spans.map_rows(query, MAX_MAP_EDGES)
        previous = await self._spans.map_rows(
            replace(query, start=start - (end - start), end=start), MAX_MAP_EDGES
        )
        response = build_map(rows, previous, (end - start).total_seconds())
        logger.info(
            "service map %s project=%s range_minutes=%d nodes=%d edges=%d duration_ms=%d",
            caller.label,
            request.project_id,
            (end - start).total_seconds() // 60,
            len(response.nodes),
            len(response.edges),
            (time.perf_counter() - started) * 1000,
        )
        return response
