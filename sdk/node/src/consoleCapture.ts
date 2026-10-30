/** Copies console.debug/log/info/warn/error calls to Spanport. The app's console output is unchanged. */

import { format } from "node:util";

import { CAPTURED_CONSOLE_METHODS } from "./constants.js";
import { type ConsoleMethod } from "./severity.js";

type ConsoleFunction = (...args: unknown[]) => void;

/**
 * Wrap the console methods so each call is also passed to `onLog`.
 *
 * The original method always runs first. A failure in `onLog` is ignored on purpose: the app's
 * console must keep working whatever happens to Spanport. A call made while `onLog` is running
 * (e.g. by an exporter that logs) is not passed on again, so it can't loop.
 *
 * @param onLog - Receives the method and the formatted message, as console would print it.
 * @returns A function that puts the original console methods back.
 */
export function captureConsole(onLog: (method: ConsoleMethod, message: string) => void): () => void {
  const originals = new Map<ConsoleMethod, ConsoleFunction>();
  let passingOn = false;
  for (const method of CAPTURED_CONSOLE_METHODS) {
    // Kept as-is so restore puts back the exact original; always called with console as `this`.
    // eslint-disable-next-line @typescript-eslint/unbound-method
    const original: ConsoleFunction = console[method];
    originals.set(method, original);
    console[method] = (...args: unknown[]): void => {
      original.apply(console, args);
      if (passingOn) return;
      passingOn = true;
      try {
        onLog(method, format(...args));
      } catch {
        // Never let Spanport break the app's console.
      } finally {
        passingOn = false;
      }
    };
  }
  return () => {
    for (const [method, original] of originals) console[method] = original;
  };
}
