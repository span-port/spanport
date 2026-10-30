import { describe, expect, it } from "vitest";

import { readEvents, takeEvents, type ServerSentEvent } from "./serverSentEvents";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => {
        controller.enqueue(encoder.encode(chunk));
      });
      controller.close();
    },
  });
}

describe("server-sent events", () => {
  it("takes complete frames, drops heartbeats and keeps the unfinished rest", () => {
    const { events, rest } = takeEvents(
      'event: logs\ndata: [{"message":"a"}]\n\n: heartbeat\n\nevent: logs\ndata: [',
    );

    expect(events).toEqual([{ event: "logs", data: '[{"message":"a"}]' }]);
    expect(rest).toBe("event: logs\ndata: [");
  });

  it("joins frames split across chunks, including a split multi-byte character", async () => {
    const events: ServerSentEvent[] = [];
    const euro = new TextEncoder().encode("€");
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: logs\ndata: ["paid '));
        controller.enqueue(euro.slice(0, 1));
        controller.enqueue(euro.slice(1));
        controller.enqueue(encoder.encode('5"]\n\n'));
        controller.close();
      },
    });

    await readEvents(body, (event) => events.push(event));

    expect(events).toEqual([{ event: "logs", data: '["paid €5"]' }]);
  });

  it("reads every event until the stream ends", async () => {
    const events: ServerSentEvent[] = [];

    await readEvents(streamOf(["event: logs\ndata: [1]\n\nevent: lo", "gs\ndata: [2]\n\n"]), (event) =>
      events.push(event),
    );

    expect(events.map((event) => event.data)).toEqual(["[1]", "[2]"]);
  });
});
