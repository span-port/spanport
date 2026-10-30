import { type Server, createServer } from "node:http";
import { type AddressInfo } from "node:net";
import { mock } from "node:test";

export const VALID_KEY = "sp_ingest_valid-test-key-00000000000000000a1b2";
export const WRONG_KEY = "sp_ingest_wrong-test-key-000000000000000000wxyz";

export interface ReceivedRequest {
  method: string;
  path: string;
  authorization: string | undefined;
  body: string;
}

export interface FakeServer {
  url: string;
  requests: ReceivedRequest[];
  stop: () => Promise<void>;
}

async function listen(server: Server): Promise<string> {
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  return `http://127.0.0.1:${String((server.address() as AddressInfo).port)}`;
}

function stopper(server: Server): () => Promise<void> {
  return () =>
    new Promise<void>((resolve) => {
      server.closeAllConnections();
      server.close(() => {
        resolve();
      });
    });
}

/** A local server playing both the collector (POST /v1/logs) and the server (key check). */
export async function startFakeSpanport(): Promise<FakeServer> {
  const requests: ReceivedRequest[] = [];
  const server = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk: Buffer) => chunks.push(chunk));
    request.on("end", () => {
      const authorization = request.headers.authorization;
      requests.push({
        method: request.method ?? "",
        path: request.url ?? "",
        authorization,
        body: Buffer.concat(chunks).toString(),
      });
      const keyAccepted = authorization === `Bearer ${VALID_KEY}`;
      response.statusCode = request.method === "GET" && !keyAccepted ? 401 : 200;
      response.setHeader("Content-Type", "application/json");
      response.end("{}");
    });
  });
  return { url: await listen(server), requests, stop: stopper(server) };
}

/** A server that redirects every request to `target`, to prove the key never follows. */
export async function startRedirectServer(target: string): Promise<FakeServer> {
  const server = createServer((_request, response) => {
    response.statusCode = 302;
    response.setHeader("Location", `${target}/stolen`);
    response.end();
  });
  return { url: await listen(server), requests: [], stop: stopper(server) };
}

/** Capture what the SDK writes to stderr. Call mock.restoreAll() afterwards. */
export function captureStderr(): () => string {
  const written: string[] = [];
  mock.method(process.stderr, "write", (chunk: string | Uint8Array) => {
    written.push(String(chunk));
    return true;
  });
  return () => written.join("");
}

/** Wait until `condition` holds, polling briefly; fail after `timeoutMs`. */
export async function waitFor(condition: () => boolean, timeoutMs = 3000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!condition()) {
    if (Date.now() > deadline) throw new Error("timed out waiting for condition");
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}
