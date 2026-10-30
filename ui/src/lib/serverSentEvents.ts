// Read server-sent events from a fetch body. EventSource can't send the Authorization header.
import { SSE_FIELD_SEPARATOR, SSE_FRAME_END, SSE_LINE_END } from "../constants/logs";

export interface ServerSentEvent {
  event: string;
  data: string;
}

/**
 * Split complete frames off the front of `buffered` text.
 *
 * @returns The parsed events (heartbeat comments are dropped) and the unfinished rest.
 */
export function takeEvents(buffered: string): { events: ServerSentEvent[]; rest: string } {
  const frames = buffered.split(SSE_FRAME_END);
  const rest = frames.pop() ?? "";
  const events = frames.map(parseFrame).filter((event) => event.data !== "");
  return { events, rest };
}

/** Parse one frame's "event:" and "data:" lines; lines starting with ":" are comments. */
function parseFrame(frame: string): ServerSentEvent {
  let event = "";
  const dataLines: string[] = [];
  for (const line of frame.split(SSE_LINE_END)) {
    const separatorAt = line.indexOf(SSE_FIELD_SEPARATOR);
    if (separatorAt <= 0) continue;
    const name = line.slice(0, separatorAt);
    const value = line.slice(separatorAt + 1).trimStart();
    if (name === "event") event = value;
    if (name === "data") dataLines.push(value);
  }
  return { event, data: dataLines.join(SSE_LINE_END) };
}

/**
 * Call `onEvent` for each event in the stream until it ends or is aborted.
 *
 * @throws Whatever reading the stream throws (an AbortError after abort).
 */
export async function readEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ServerSentEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    // stream: true keeps a multi-byte character split across chunks intact.
    const { events, rest } = takeEvents(buffered + decoder.decode(value, { stream: true }));
    buffered = rest;
    events.forEach(onEvent);
  }
}
