/**
 * Traces: each request the app handles, and each step inside it (outgoing HTTP and fetch calls,
 * Postgres queries, Express and NestJS routes, decorated controllers and services), sent in the
 * background to the collector's /v1/traces.
 */

import { createRequire } from "node:module";

import { context, propagation, trace } from "@opentelemetry/api";
import { AsyncLocalStorageContextManager } from "@opentelemetry/context-async-hooks";
import { W3CTraceContextPropagator } from "@opentelemetry/core";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { ExpressInstrumentation } from "@opentelemetry/instrumentation-express";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";
import { PgInstrumentation } from "@opentelemetry/instrumentation-pg";
import { UndiciInstrumentation } from "@opentelemetry/instrumentation-undici";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { BatchSpanProcessor, type SpanExporter, TracerProvider } from "@opentelemetry/sdk-trace";

import {
  AUTHORIZATION_HEADER,
  BEARER_PREFIX,
  OTLP_TRACES_PATH,
  PATCHED_BUILTINS,
  SERVICE_NAME_ATTRIBUTE,
} from "./constants.js";
import { joinUrl } from "./urls.js";

export interface ActiveTracing {
  provider: TracerProvider;
  /** Send what is queued, then stop tracing and put the globals back. */
  stop: () => Promise<void>;
}

/** Hosts the SDK itself talks to; requests to them are never traced, so Spanport never traces itself. */
export interface OwnHosts {
  collectorUrl: string;
  serverUrl: string;
}

/**
 * Exporter that sends span batches to the collector with the data key as a bearer token.
 *
 * @param collectorUrl - Base URL of the OTel Collector, e.g. "http://localhost:4318".
 * @param dataKey - The raw data key.
 */
export function buildTraceExporter(collectorUrl: string, dataKey: string): OTLPTraceExporter {
  return new OTLPTraceExporter({
    url: joinUrl(collectorUrl, OTLP_TRACES_PATH),
    headers: { [AUTHORIZATION_HEADER]: BEARER_PREFIX + dataKey },
  });
}

/**
 * Start tracing: keep the current request across awaits, register the tracer provider and switch
 * on timing for HTTP, fetch, Postgres and Express (each only does something if the app uses that
 * library, and only for libraries loaded after this runs).
 *
 * @param service - Service name shown in Spanport.
 * @param exporter - Where span batches go; OTLP in real use, in-memory in tests.
 * @param ownHosts - The SDK's own collector and server, never traced.
 * @returns The running tracing, and how to stop it.
 */
export function startTracing(service: string, exporter: SpanExporter, ownHosts: OwnHosts): ActiveTracing {
  const contextManager = new AsyncLocalStorageContextManager().enable();
  context.setGlobalContextManager(contextManager);
  // Outgoing calls carry a W3C traceparent header, so another service running the SDK joins
  // the same trace (Spanport then shows the call as a service call).
  propagation.setGlobalPropagator(new W3CTraceContextPropagator());
  const provider = new TracerProvider({
    resource: resourceFromAttributes({ [SERVICE_NAME_ATTRIBUTE]: service }),
    spanProcessors: [new BatchSpanProcessor({ exporter })],
  });
  trace.setGlobalTracerProvider(provider);
  useHttpInstrumentation(provider, ownHosts);
  const unregisterLibraries = registerInstrumentations({
    tracerProvider: provider,
    instrumentations: [
      new ExpressInstrumentation(),
      new PgInstrumentation(),
      new UndiciInstrumentation({
        ignoreRequestHook: (request) => ownHostsOf(ownHosts).has(new URL(request.origin).host),
      }),
    ],
  });
  return {
    provider,
    stop: async () => {
      unregisterLibraries();
      // The HTTP instrumentation stays on (see useHttpInstrumentation); with its provider shut
      // down, the spans it makes go nowhere.
      await provider.shutdown();
      trace.disable();
      context.disable();
      propagation.disable();
    },
  };
}

// The HTTP instrumentation is switched on once per process and stays on. Node's http module is
// patched when it is require()d, which happens once; switched off, the instrumentation can't
// patch it again, so a later init() (after shutdown()) would time nothing.
let httpInstrumentation: HttpInstrumentation | undefined;

/**
 * Time incoming requests and outgoing http/https calls (except the SDK's own) into `provider`.
 */
function useHttpInstrumentation(provider: TracerProvider, ownHosts: OwnHosts): void {
  const ownOrigins = ownHostsOf(ownHosts);
  const config = {
    ignoreOutgoingRequestHook: (request: Parameters<typeof outgoingHost>[0]) => ownOrigins.has(outgoingHost(request)),
  };
  if (httpInstrumentation) {
    httpInstrumentation.setConfig(config);
    httpInstrumentation.setTracerProvider(provider);
    return;
  }
  httpInstrumentation = new HttpInstrumentation(config);
  registerInstrumentations({ tracerProvider: provider, instrumentations: [httpInstrumentation] });
  // Node's http/https are usually loaded already, and ESM imports never go through require, so
  // require them once now: that patches the shared module object ESM and CommonJS code both use.
  for (const builtin of PATCHED_BUILTINS) requireFromApp(builtin);
}

/** "host:port" of an outgoing request, as URL.host writes it (no port for the default one). */
function outgoingHost(request: {
  host?: string | null | undefined;
  hostname?: string | null | undefined;
  port?: string | number | null | undefined;
}): string {
  const host = request.hostname ?? request.host ?? "";
  return request.port ? `${host}:${String(request.port)}` : host;
}

/** "host:port" of the SDK's own collector and server (calls to them, like the key check, aren't timed). */
function ownHostsOf(ownHosts: OwnHosts): Set<string> {
  return new Set([new URL(ownHosts.collectorUrl).host, new URL(ownHosts.serverUrl).host]);
}

const requireFromApp = createRequire(import.meta.url);
