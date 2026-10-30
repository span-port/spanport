// Turn a typed name into the slug the server stores, e.g. "Tracking API" → "tracking-api".
import {
  EDGE_SEPARATORS,
  NOT_SLUG_CHARACTERS,
  SLUG_MAX_LENGTH,
  SLUG_SEPARATOR,
} from "../constants/setup";

/** Lower case, every other run of characters one dash, no dashes at the ends, at most 63 long. */
export function toSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(NOT_SLUG_CHARACTERS, SLUG_SEPARATOR)
    .replace(EDGE_SEPARATORS, "")
    .slice(0, SLUG_MAX_LENGTH)
    .replace(EDGE_SEPARATORS, "");
}
