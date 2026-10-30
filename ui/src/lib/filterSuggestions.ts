// The filter box's dropdown: property, then operator, then value, like the EC2 search bar.
import {
  CLIENT_IP_ATTRIBUTE,
  CONTAINS_OPERATOR,
  FILTER_PROPERTIES,
  MAIN_LEVELS,
  MAX_SUGGESTIONS,
  MESSAGE_FIELD,
  USER_ID_ATTRIBUTE,
} from "../constants/logs";
import type { FilterChip, FilterOperator, LogItem } from "../features/logs/types";

/** How far the user is in building a chip. */
export type FilterStage =
  | { step: "property" }
  | { step: "operator"; field: string }
  | { step: "value"; field: string; operator: FilterOperator };

/** What choosing a dropdown item does. */
export type FilterChoice =
  | { action: "property"; field: string }
  | { action: "operator"; operator: FilterOperator }
  | { action: "chip"; chip: FilterChip };

export interface FilterSuggestion {
  label: string;
  detail: string;
  choice: FilterChoice;
}

/** An operator in words, e.g. "Does not contain" for "!:". */
export function operatorName(operator: FilterOperator): string {
  switch (operator) {
    case "=":
      return "Equals";
    case "!=":
      return "Does not equal";
    case ":":
      return "Contains";
    case "!:":
      return "Does not contain";
  }
}

/** The label for a field, e.g. "Client IP" for ip; other attribute names show as is. */
export function propertyLabel(field: string): string {
  return FILTER_PROPERTIES.find((property) => property.field === field)?.label ?? field;
}

/** The text before the input while a chip is being built, e.g. "Level =". */
export function stagePrefix(stage: FilterStage): string {
  if (stage.step === "property") return "";
  if (stage.step === "operator") return propertyLabel(stage.field);
  return `${propertyLabel(stage.field)} ${stage.operator}`;
}

/** What Enter does with the typed text: plain text searches messages; a value finishes the chip. */
export function enterChoice(stage: FilterStage, typed: string): FilterChoice | null {
  const value = typed.trim();
  if (value === "") return null;
  if (stage.step === "property") {
    return { action: "chip", chip: { field: MESSAGE_FIELD, operator: CONTAINS_OPERATOR, value } };
  }
  if (stage.step === "value") {
    return { action: "chip", chip: { field: stage.field, operator: stage.operator, value } };
  }
  return null;
}

/**
 * The dropdown for the current step.
 *
 * @param rows - Logs on screen; values for service, IP and user are suggested from them.
 */
export function filterSuggestions(
  stage: FilterStage,
  typed: string,
  rows: LogItem[],
): { title: string; items: FilterSuggestion[] } {
  const needle = typed.trim().toLowerCase();
  if (stage.step === "property") {
    const items: FilterSuggestion[] = FILTER_PROPERTIES.filter((property) =>
      property.label.toLowerCase().includes(needle),
    ).map((property) => ({
      label: property.label,
      detail: property.hint,
      choice: { action: "property", field: property.field },
    }));
    const searchText = enterChoice(stage, typed);
    if (searchText) items.push({ label: `Message contains "${typed.trim()}"`, detail: "press Enter", choice: searchText });
    return { title: "Properties", items };
  }
  if (stage.step === "operator") {
    const operators = FILTER_PROPERTIES.find((property) => property.field === stage.field)?.operators ?? [];
    const items: FilterSuggestion[] = operators.map((operator) => ({
      label: operatorName(operator),
      detail: operator,
      choice: { action: "operator", operator },
    }));
    return { title: `Operators for ${propertyLabel(stage.field)}`, items };
  }
  const items: FilterSuggestion[] = knownValues(stage.field, rows)
    .filter((value) => value.toLowerCase().includes(needle))
    .slice(0, MAX_SUGGESTIONS)
    .map((value) => ({
      label: value,
      detail: "",
      choice: { action: "chip", chip: { field: stage.field, operator: stage.operator, value } },
    }));
  const typedValue = enterChoice(stage, typed);
  if (typedValue) items.unshift({ label: `Use "${typed.trim()}"`, detail: "press Enter", choice: typedValue });
  return { title: "Values", items };
}

/** Values seen for `field`, most frequent first. Levels are always offered. */
function knownValues(field: string, rows: LogItem[]): string[] {
  if (field === "level") return [...MAIN_LEVELS];
  const read = valueReader(field);
  if (read === null) return [];
  const counts = new Map<string, number>();
  for (const row of rows) {
    const value = read(row);
    if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()].sort((first, second) => second[1] - first[1]).map(([value]) => value);
}

/** How to read `field` from a log line, or null when values aren't suggested for it. */
function valueReader(field: string): ((row: LogItem) => string | undefined) | null {
  switch (field) {
    case "service":
      return (row) => row.service;
    case "ip":
      return (row) => row.attributes[CLIENT_IP_ATTRIBUTE];
    case "user":
      return (row) => row.attributes[USER_ID_ATTRIBUTE];
    default:
      return null;
  }
}
