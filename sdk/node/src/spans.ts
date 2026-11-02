/**
 * Your own steps in a trace: `withSpan(name, fn)` for any block, and the `trace()` class decorator
 * that times every method of a controller or service as "ClassName.method".
 */

import { type Span, SpanStatusCode, trace as otelTrace } from "@opentelemetry/api";

import {
  ANONYMOUS_CLASS_NAME,
  CONSTRUCTOR_NAME,
  SDK_SCOPE_NAME,
  SPAN_NAME_SEPARATOR,
} from "./constants.js";

type AnyFunction = (this: unknown, ...args: unknown[]) => unknown;

/** Reflect metadata (reflect-metadata, loaded by NestJS); absent in plain apps. */
interface MetadataReflect {
  getMetadataKeys?: (target: object) => unknown[];
  getMetadata?: (key: unknown, target: object) => unknown;
  defineMetadata?: (key: unknown, value: unknown, target: object) => void;
}

/**
 * Run `work` inside a span named `name`, nested under the current one. Works for sync and async
 * work; a thrown error or rejected promise marks the span failed and is rethrown unchanged.
 *
 *     const user = await spanport.withSpan("load user", () => repo.find(id));
 *
 * @returns Whatever `work` returns.
 */
export function withSpan<T>(name: string, work: () => T): T {
  return otelTrace.getTracer(SDK_SCOPE_NAME).startActiveSpan(name, (span) => {
    try {
      const result = work();
      if (result instanceof Promise) {
        return result.then(
          (value: unknown) => {
            span.end();
            return value;
          },
          (error: unknown) => {
            fail(span, error);
            throw error;
          },
        ) as T;
      }
      span.end();
      return result;
    } catch (error) {
      fail(span, error);
      throw error;
    }
  });
}

function fail(span: Span, error: unknown): void {
  span.recordException(error instanceof Error ? error : String(error));
  span.setStatus({ code: SpanStatusCode.ERROR, message: error instanceof Error ? error.message : String(error) });
  span.end();
}

/**
 * Class decorator: every method becomes a step of the trace, named "ClassName.method".
 *
 *     @spanport.trace()
 *     @Injectable()
 *     export class VariablesService { ... }
 *
 * Works with TypeScript's legacy decorators (NestJS) and standard ones. Method metadata (e.g.
 * NestJS route paths) is copied to the timed method, so frameworks keep working.
 *
 * @param name - The name used before the dot; the class's own name by default.
 */
export function trace(name?: string) {
  // Standard decorators also pass a context object; it isn't needed, so it isn't declared.
  return (target: abstract new (...args: never[]) => unknown): void => {
    const className = name ?? (target.name || ANONYMOUS_CLASS_NAME);
    const prototype = target.prototype as Record<string, unknown>;
    for (const methodName of Object.getOwnPropertyNames(prototype)) {
      const descriptor = Object.getOwnPropertyDescriptor(prototype, methodName);
      if (methodName === CONSTRUCTOR_NAME || typeof descriptor?.value !== "function") continue;
      const timed = timedMethod(`${className}${SPAN_NAME_SEPARATOR}${methodName}`, descriptor.value as AnyFunction);
      Object.defineProperty(prototype, methodName, { ...descriptor, value: timed });
    }
  };
}

/** A method that runs the original inside a span, carrying over its name and metadata. */
function timedMethod(spanName: string, original: AnyFunction): AnyFunction {
  const timed = function (this: unknown, ...args: unknown[]): unknown {
    return withSpan(spanName, () => original.apply(this, args));
  };
  Object.defineProperty(timed, "name", { value: original.name });
  copyMetadata(original, timed);
  return timed;
}

/** Copy reflect-metadata entries (NestJS route paths, guards...) from one function to another. */
function copyMetadata(from: AnyFunction, to: AnyFunction): void {
  const reflect = Reflect as unknown as MetadataReflect;
  if (!reflect.getMetadataKeys || !reflect.getMetadata || !reflect.defineMetadata) return;
  for (const key of reflect.getMetadataKeys(from)) {
    reflect.defineMetadata(key, reflect.getMetadata(key, from), to);
  }
}
