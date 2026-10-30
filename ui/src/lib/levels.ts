// Which status color a log level is shown in.

export type LevelTone = "error" | "warn" | "info" | "debug";

/** The tone for a level name from the server (TRACE, DEBUG, INFO, WARN, ERROR, FATAL). */
export function levelTone(level: string): LevelTone {
  switch (level) {
    case "FATAL":
    case "ERROR":
      return "error";
    case "WARN":
      return "warn";
    case "INFO":
      return "info";
    default:
      return "debug";
  }
}
