import { levelTone } from "../../../lib/levels";

/** A log level in its status color: red for errors, amber for warnings. */
export function LevelTag({ level }: { level: string }) {
  return <span className={`level-tag level-${levelTone(level)}`}>{level}</span>;
}
