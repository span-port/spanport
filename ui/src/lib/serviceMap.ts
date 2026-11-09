// Pure helpers for the service map: where each box goes, the lines between them, and their words.
import { URL_PARAM_PROJECT } from "../constants/logs";
import {
  MAP_CALL_NAMES,
  MAP_COLUMN_GAP,
  MAP_KIND_NAMES,
  MAP_LABEL_LIFT,
  MAP_NODE_HEIGHT,
  MAP_NODE_WIDTH,
  MAP_ROW_GAP,
  MIN_RATE_PER_SECOND,
  SECONDS_PER_MINUTE,
} from "../constants/traces";
import { APIS_ROUTE, ERRORS_ROUTE, REQUESTS_ROUTE } from "../constants/ui";
import type { MapEdge, MapKind, MapNode, ServiceMap } from "../features/endpoints/api";
import { requestShare } from "./errors";
import { writeRange, type RangeSelection } from "./timeRange";
import { formatDuration } from "./waterfall";

export interface PlacedNode {
  node: MapNode;
  x: number;
  y: number;
}

export interface PlacedEdge {
  edge: MapEdge;
  path: string;
  labelX: number;
  labelY: number;
}

// Boxes in a column: your services first, then databases, other systems and LLM providers.
const KIND_ORDER: readonly MapKind[] = ["service", "db", "external", "llm"];

/**
 * How many steps each box is from a service nobody of yours calls: those start on the left,
 * the services they call one column right, and so on; anything else sits right of its callers.
 */
export function mapColumns(map: ServiceMap): Map<string, number> {
  const columns = new Map(map.nodes.map((node) => [node.id, 0]));
  // Each round pushes callees right of their callers; as many rounds as boxes, so a loop of
  // services that call each other still stops.
  let roundsLeft = map.nodes.length;
  while (roundsLeft > 0) {
    roundsLeft -= 1;
    for (const edge of map.edges) {
      const next = (columns.get(edge.source) ?? 0) + 1;
      if (next > (columns.get(edge.target) ?? 0)) columns.set(edge.target, Math.min(next, map.nodes.length));
    }
  }
  return columns;
}

/** Every box's top-left corner and every line's curve, with the drawing's size. */
export function mapLayout(map: ServiceMap): { nodes: PlacedNode[]; edges: PlacedEdge[]; width: number; height: number } {
  const columns = mapColumns(map);
  const byColumn = new Map<number, MapNode[]>();
  for (const node of map.nodes) {
    const column = columns.get(node.id) ?? 0;
    byColumn.set(column, [...(byColumn.get(column) ?? []), node]);
  }
  const tallest = Math.max(1, ...[...byColumn.values()].map((nodes) => nodes.length));
  const height = tallest * MAP_NODE_HEIGHT + (tallest - 1) * MAP_ROW_GAP;
  const placed = new Map<string, PlacedNode>();
  for (const [column, nodes] of byColumn) {
    const sorted = [...nodes].sort(
      (left, right) => KIND_ORDER.indexOf(left.kind) - KIND_ORDER.indexOf(right.kind) || left.name.localeCompare(right.name),
    );
    const columnHeight = sorted.length * MAP_NODE_HEIGHT + (sorted.length - 1) * MAP_ROW_GAP;
    sorted.forEach((node, row) => {
      placed.set(node.id, {
        node,
        x: column * (MAP_NODE_WIDTH + MAP_COLUMN_GAP),
        y: (height - columnHeight) / 2 + row * (MAP_NODE_HEIGHT + MAP_ROW_GAP),
      });
    });
  }
  const columnCount = Math.max(1, ...[...byColumn.keys()].map((column) => column + 1));
  return {
    nodes: [...placed.values()],
    edges: map.edges.flatMap((edge) => {
      const from = placed.get(edge.source);
      const to = placed.get(edge.target);
      return from && to ? [placeEdge(edge, from, to)] : [];
    }),
    width: columnCount * MAP_NODE_WIDTH + (columnCount - 1) * MAP_COLUMN_GAP,
    height,
  };
}

function placeEdge(edge: MapEdge, from: PlacedNode, to: PlacedNode): PlacedEdge {
  const startX = from.x + MAP_NODE_WIDTH;
  const startY = from.y + MAP_NODE_HEIGHT / 2;
  const endX = to.x;
  const endY = to.y + MAP_NODE_HEIGHT / 2;
  const middleX = (startX + endX) / 2;
  return {
    edge,
    path: `M${String(startX)} ${String(startY)} C ${String(middleX)} ${String(startY)}, ${String(middleX)} ${String(endY)}, ${String(endX)} ${String(endY)}`,
    labelX: middleX,
    labelY: (startY + endY) / 2 - MAP_LABEL_LIFT,
  };
}

/**
 * Calls over the range as a rate, e.g. "120/s", "1.5/s" or "4/min"; null under one a minute,
 * where a rate reads as "0.0/min" and the count says more.
 */
export function rateText(calls: number, rangeSeconds: number): string | null {
  const perSecond = rangeSeconds > 0 ? calls / rangeSeconds : 0;
  if (perSecond >= 10) return `${String(Math.round(perSecond))}/s`;
  if (perSecond >= MIN_RATE_PER_SECOND) return `${perSecond.toFixed(1)}/s`;
  const perMinute = perSecond * SECONDS_PER_MINUTE;
  return perMinute >= 1 ? `${String(Math.round(perMinute))}/min` : null;
}

/**
 * Calls with what they are, as a rate when busy ("310 queries/s", "1 query/min"), else a count
 * ("30 req", "1 query").
 */
export function callsText(calls: number, rangeSeconds: number, callName: { one: string; many: string }): string {
  const rate = rateText(calls, rangeSeconds);
  const amount = rate ?? calls.toLocaleString("en");
  const name = amount.startsWith("1/") || amount === "1" ? callName.one : callName.many;
  return rate ? rate.replace("/", ` ${name}/`) : `${amount} ${name}`;
}

/** A line's words, e.g. "310 queries/s · 4.0 ms", or its failures when they are too many. */
export function edgeLabel(edge: MapEdge, targetKind: MapKind, rangeSeconds: number): string {
  const detail =
    edge.status === "bad" ? `${requestShare(edge.errors, edge.calls)} errors` : formatDuration(edge.p50_ms);
  return `${callsText(edge.calls, rangeSeconds, MAP_CALL_NAMES[targetKind])} · ${detail}`;
}

/** The details panel's facts about one box, as (name, value) pairs. */
export function nodeFacts(node: MapNode, rangeSeconds: number): [string, string][] {
  const callName = node.kind === "service" ? "Requests" : node.kind === "db" ? "Queries" : "Calls";
  const facts: [string, string][] = [
    [callName, callCount(node.calls, rangeSeconds)],
    ["Errors", requestShare(node.errors, node.calls)],
    ["Typical time (p50)", formatDuration(node.p50_ms)],
    ["Slowest 5% (p95)", formatDuration(node.p95_ms)],
  ];
  if (node.kind === "service") facts.push(["Calls", node.calls_to.join(", ") || "Nothing else"]);
  facts.push(["Called by", node.called_by.join(", ") || "Requests from outside"]);
  return facts;
}

/** A count with its rate when busy enough, e.g. "1,158 (4/min)" or "30". */
function callCount(calls: number, rangeSeconds: number): string {
  const rate = rateText(calls, rangeSeconds);
  return rate ? `${calls.toLocaleString("en")} (${rate})` : calls.toLocaleString("en");
}

/** What a kind of box is, e.g. "Database". */
export function kindName(kind: MapKind): string {
  return MAP_KIND_NAMES[kind];
}

/** Where to look next from a box: its APIs, its errors, or the requests that call it. */
export function nodeLink(node: MapNode, projectId: string, range: RangeSelection): { label: string; to: string } {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId });
  if (node.kind === "service" || node.kind === "db") {
    writeRange(range, params);
    return { label: node.kind === "db" ? "See slow queries" : "Open APIs", to: `${APIS_ROUTE}?${params.toString()}` };
  }
  if (node.status === "bad") {
    writeRange(range, params);
    return { label: "See the errors", to: `${ERRORS_ROUTE}?${params.toString()}` };
  }
  return { label: "Open Requests", to: `${REQUESTS_ROUTE}?${params.toString()}` };
}
