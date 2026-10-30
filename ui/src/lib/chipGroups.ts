// Show filter chips grouped by property, the way the server reads them: values of one property are
// alternatives ("Service is one of: api, worker"), different properties must all match.
import { EQUALS_OPERATOR, LEVEL_FIELD } from "../constants/logs";
import type { FilterChip, FilterOperator } from "../features/logs/types";

export interface ChipGroup {
  field: string;
  operator: FilterOperator;
  /** Each value with its chip's position, so one value can be removed. */
  values: { value: string; index: number }[];
}

/** A "Level = X" chip: the level cards own these, so the chip area doesn't show them. */
export function isLevelChip(chip: FilterChip): boolean {
  return chip.field === LEVEL_FIELD && chip.operator === EQUALS_OPERATOR;
}

/** The chips other than levels, grouped by property and operator, in the order first added. */
export function groupChips(chips: FilterChip[]): ChipGroup[] {
  const groups = new Map<string, ChipGroup>();
  chips.forEach((chip, index) => {
    if (isLevelChip(chip)) return;
    const groupKey = `${chip.field}${chip.operator}`;
    const group = groups.get(groupKey) ?? { field: chip.field, operator: chip.operator, values: [] };
    group.values.push({ value: chip.value, index });
    groups.set(groupKey, group);
  });
  return [...groups.values()];
}

/** How a group reads, e.g. "is one of" for two or more equals values. */
export function groupVerb(operator: FilterOperator, valueCount: number): string {
  switch (operator) {
    case "=":
      return valueCount > 1 ? "is one of" : "is";
    case "!=":
      return "is not";
    case ":":
      return valueCount > 1 ? "contains one of" : "contains";
    case "!:":
      return "doesn't contain";
  }
}
