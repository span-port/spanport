/** Maps console, pino and winston levels to OpenTelemetry severities. */

import { SeverityNumber } from "@opentelemetry/api";

import {
  type CAPTURED_CONSOLE_METHODS,
  PINO_DEBUG,
  PINO_ERROR,
  PINO_FATAL,
  PINO_INFO,
  PINO_WARN,
} from "./constants.js";

export type ConsoleMethod = (typeof CAPTURED_CONSOLE_METHODS)[number];

export interface Severity {
  number: SeverityNumber;
  text: string;
}

const TRACE: Severity = { number: SeverityNumber.TRACE, text: "TRACE" };
const DEBUG: Severity = { number: SeverityNumber.DEBUG, text: "DEBUG" };
export const INFO: Severity = { number: SeverityNumber.INFO, text: "INFO" };
const WARN: Severity = { number: SeverityNumber.WARN, text: "WARN" };
const ERROR: Severity = { number: SeverityNumber.ERROR, text: "ERROR" };
const FATAL: Severity = { number: SeverityNumber.FATAL, text: "FATAL" };

/**
 * Severity of a console call.
 *
 * @param method - The console method that was called.
 * @returns console.debug is DEBUG, log and info are INFO, warn is WARN, error is ERROR.
 */
export function consoleSeverity(method: ConsoleMethod): Severity {
  switch (method) {
    case "debug":
      return DEBUG;
    case "log":
    case "info":
      return INFO;
    case "warn":
      return WARN;
    case "error":
      return ERROR;
  }
}

/**
 * Severity of a pino level number (10 trace ... 60 fatal; custom levels fall into the band below).
 *
 * @param level - pino's numeric level.
 * @returns The matching severity.
 */
export function pinoSeverity(level: number): Severity {
  if (level >= PINO_FATAL) return FATAL;
  if (level >= PINO_ERROR) return ERROR;
  if (level >= PINO_WARN) return WARN;
  if (level >= PINO_INFO) return INFO;
  if (level >= PINO_DEBUG) return DEBUG;
  return TRACE;
}

/**
 * Severity of a winston (npm-style) level name. Unknown names count as INFO.
 *
 * @param level - e.g. "error", "warn", "info", "http", "verbose", "debug", "silly".
 * @returns The matching severity.
 */
export function winstonSeverity(level: string): Severity {
  switch (level.toLowerCase()) {
    case "fatal":
    case "emerg":
    case "alert":
    case "crit":
      return FATAL;
    case "error":
      return ERROR;
    case "warn":
    case "warning":
      return WARN;
    case "debug":
    case "verbose":
      return DEBUG;
    case "silly":
    case "trace":
      return TRACE;
    default:
      return INFO;
  }
}
