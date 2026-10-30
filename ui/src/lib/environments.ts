// Which environments the picker offers, and catching near-duplicates such as "prod" vs "production".
import { ENVIRONMENTS } from "../constants/setup";

/**
 * The standard environments first, then ones the organization already uses, then ones added
 * on this page; each once.
 */
export function environmentChoices(used: string[], added: string[]): string[] {
  return [...new Set([...ENVIRONMENTS.map((choice) => choice.value), ...used, ...added])];
}

/**
 * An existing environment that looks like the same thing under another name, or null.
 *
 * "prod" and "production" (one starts the other) are flagged; an exact match is not, since
 * picking an existing environment is fine.
 */
export function similarEnvironment(candidate: string, existing: string[]): string | null {
  if (candidate === "") return null;
  return (
    existing.find(
      (name) => name !== candidate && (name.startsWith(candidate) || candidate.startsWith(name)),
    ) ?? null
  );
}

/** The label for an environment: the standard ones have one, others show their slug. */
export function environmentLabel(environment: string): string {
  return ENVIRONMENTS.find((choice) => choice.value === environment)?.label ?? environment;
}
