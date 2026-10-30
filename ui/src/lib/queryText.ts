// Write filter chips as text in the query language, e.g. level:ERROR AND "payment failed".
import {
  CONTAINS_OPERATORS,
  MESSAGE_FIELD,
  NEGATIVE_OPERATORS,
  QUERY_AND,
  QUERY_NOT,
  QUERY_OR,
  QUERY_QUOTE,
  QUERY_VALUE_NEEDS_QUOTES,
  QUERY_WILDCARD,
} from "../constants/logs";
import type { FilterChip } from "../features/logs/types";

/** One chip as query text: message chips become phrases, "contains" becomes *value*. */
function chipText(chip: FilterChip): string {
  const sign = NEGATIVE_OPERATORS.includes(chip.operator) ? QUERY_NOT : "";
  const unquoted = chip.value.replaceAll(QUERY_QUOTE, "");
  if (chip.field === MESSAGE_FIELD) return `${sign}${QUERY_QUOTE}${unquoted}${QUERY_QUOTE}`;
  const value = CONTAINS_OPERATORS.includes(chip.operator)
    ? `${QUERY_WILDCARD}${unquoted}${QUERY_WILDCARD}`
    : unquoted;
  const written = QUERY_VALUE_NEEDS_QUOTES.test(value) ? `${QUERY_QUOTE}${value}${QUERY_QUOTE}` : value;
  return `${sign}${chip.field}:${written}`;
}

/**
 * The chips as one query, with the server's rule: values of one field are alternatives (OR),
 * exclusions all hold, and different fields must all match (AND).
 *
 * Used to show what a search runs as, and to carry chips over when switching to a text query.
 */
export function chipsToQueryText(chips: FilterChip[]): string {
  const groups = Map.groupBy(chips, (chip) => `${chip.field}${chip.operator}`);
  return [...groups.values()]
    .map((group) => {
      const negative = NEGATIVE_OPERATORS.includes(group[0]?.operator ?? "=");
      if (group.length === 1 || negative) return group.map(chipText).join(QUERY_AND);
      return `(${group.map(chipText).join(QUERY_OR)})`;
    })
    .join(QUERY_AND);
}
