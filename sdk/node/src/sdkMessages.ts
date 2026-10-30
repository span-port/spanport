/**
 * The SDK's own messages. They go straight to stderr: never through console (which the SDK may be
 * capturing, so they would loop) and never exported.
 */

import { SDK_MESSAGE_PREFIX } from "./constants.js";

type MessageLevel = "INFO" | "WARNING" | "ERROR";

function write(level: MessageLevel, message: string): void {
  process.stderr.write(`${level} ${SDK_MESSAGE_PREFIX} ${message}\n`);
}

/** Report normal progress, e.g. the key was accepted. */
export function sdkInfo(message: string): void {
  write("INFO", message);
}

/** Report something that may stop logs from arriving, e.g. the server could not be reached. */
export function sdkWarning(message: string): void {
  write("WARNING", message);
}

/** Report something that stops logs from being stored, e.g. a rejected key. */
export function sdkError(message: string): void {
  write("ERROR", message);
}
