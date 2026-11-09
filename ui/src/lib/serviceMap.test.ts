import { describe, expect, it } from "vitest";

import type { MapEdge, MapNode, ServiceMap } from "../features/endpoints/api";
import { edgeLabel, mapColumns, mapLayout, nodeFacts, nodeLink, rateText } from "./serviceMap";

function node(id: string, changes: Partial<MapNode> = {}): MapNode {
  const [kind, name] = id.split(":") as [MapNode["kind"], string];
  return { id, kind, name, calls: 3600, errors: 0, p50_ms: 4, p95_ms: 9, status: "ok", calls_to: [], called_by: [], ...changes };
}

function edge(source: string, target: string, changes: Partial<MapEdge> = {}): MapEdge {
  return { source, target, calls: 3600, errors: 0, p50_ms: 4, p95_ms: 9, status: "ok", ...changes };
}

const MAP: ServiceMap = {
  range_seconds: 3600,
  nodes: [node("db:postgresql"), node("service:billing"), node("service:api"), node("external:api.mailgun.net")],
  edges: [
    edge("service:api", "service:billing"),
    edge("service:billing", "db:postgresql"),
    edge("service:api", "external:api.mailgun.net"),
  ],
};

describe("Service map helpers", () => {
  it("puts callers left of what they call", () => {
    const columns = mapColumns(MAP);
    expect([columns.get("service:api"), columns.get("service:billing"), columns.get("db:postgresql")]).toEqual([0, 1, 2]);
    expect(columns.get("external:api.mailgun.net")).toBe(1);

    const loop = mapColumns({ ...MAP, edges: [edge("service:api", "service:billing"), edge("service:billing", "service:api")] });
    expect(Math.max(...loop.values())).toBeLessThanOrEqual(MAP.nodes.length);
  });

  it("places boxes in columns, services first, with a curve for every line", () => {
    const layout = mapLayout(MAP);
    const billing = layout.nodes.find((placed) => placed.node.id === "service:billing");
    const mail = layout.nodes.find((placed) => placed.node.id === "external:api.mailgun.net");

    expect(billing?.x).toBe(mail?.x);
    expect((billing?.y ?? 0) < (mail?.y ?? 0)).toBe(true);
    expect(layout.edges).toHaveLength(3);
    expect(layout.edges[0]?.path.startsWith("M180 ")).toBe(true);
    expect(layout.width).toBe(3 * 180 + 2 * 200);
  });

  it("writes rates, line labels and facts", () => {
    expect([rateText(432_000, 3600), rateText(5400, 3600), rateText(60, 3600), rateText(6, 3600)]).toEqual([
      "120/s",
      "1.5/s",
      "1/min",
      null,
    ]);
    expect(edgeLabel(edge("a", "b", { calls: 30, p50_ms: 433 }), "external", 604_800)).toBe("30 req · 433 ms");
    expect(edgeLabel(edge("a", "b", { calls: 60, p50_ms: 1.2 }), "db", 3600)).toBe("1 query/min · 1.2 ms");
    expect(edgeLabel(edge("a", "b", { calls: 1, p50_ms: 1.2 }), "db", 3600)).toBe("1 query · 1.2 ms");
    expect(edgeLabel(edge("service:api", "db:postgresql", { calls: 1_116_000 }), "db", 3600)).toBe("310 queries/s · 4.0 ms");
    expect(edgeLabel(edge("a", "b", { calls: 1000, errors: 26, status: "bad" }), "external", 3600)).toBe(
      "0.3 req/s · 2.60% errors",
    );
    const facts = nodeFacts(node("service:api", { calls_to: ["billing"] }), 3600);
    expect(facts.map(([name]) => name)).toEqual([
      "Requests",
      "Errors",
      "Typical time (p50)",
      "Slowest 5% (p95)",
      "Calls",
      "Called by",
    ]);
  });

  it("links a box to where to look next", () => {
    const range = { kind: "preset", key: "1h" } as const;
    expect(nodeLink(node("db:postgresql"), "p1", range).label).toBe("See slow queries");
    expect(nodeLink(node("external:mail", { status: "bad" }), "p1", range).to.startsWith("/errors?project=p1")).toBe(true);
    expect(nodeLink(node("llm:openai"), "p1", range).to).toBe("/requests?project=p1");
  });
});
