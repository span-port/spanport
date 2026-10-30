// The explorer's state lives in the URL, so a search can be bookmarked or shared.
import * as zod from "zod";

import {
  MAX_FILTER_CHIPS,
  MAX_FILTER_VALUE_LENGTH,
  MODE_QUERY,
  URL_PARAM_COMBINE,
  URL_PARAM_FILTERS,
  URL_PARAM_MODE,
  URL_PARAM_PROJECT,
  URL_PARAM_QUERY,
} from "../constants/logs";
import type { FilterChip, FilterCombine } from "../features/logs/types";
import { readRange, writeRange, type RangeSelection } from "./timeRange";

export interface LogUrlState {
  projectId: string | null;
  range: RangeSelection;
  filters: FilterChip[];
  combine: FilterCombine;
  query: string;
  /** True when the advanced text query replaces the filter chips. */
  queryMode: boolean;
}

/** One filter chip, as the server accepts it. */
export const filterChipSchema = zod.object({
  field: zod.string().min(1),
  operator: zod.enum(["=", "!=", ":", "!:"]),
  value: zod.string().trim().min(1).max(MAX_FILTER_VALUE_LENGTH),
});

const filtersSchema = zod.array(filterChipSchema).max(MAX_FILTER_CHIPS);

/** Read the explorer state from URL params; anything missing or malformed falls back to defaults. */
export function readLogUrlState(params: URLSearchParams): LogUrlState {
  return {
    projectId: params.get(URL_PARAM_PROJECT),
    range: readRange(params),
    filters: readFilters(params.get(URL_PARAM_FILTERS)),
    combine: params.get(URL_PARAM_COMBINE) === "or" ? "or" : "and",
    query: params.get(URL_PARAM_QUERY) ?? "",
    queryMode: params.get(URL_PARAM_MODE) === MODE_QUERY,
  };
}

/** Parse the filters param (JSON); a hand-edited, broken value means no filters. */
function readFilters(raw: string | null): FilterChip[] {
  if (raw === null) return [];
  try {
    const parsed = filtersSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : [];
  } catch {
    return [];
  }
}

/** URL params for `state`, leaving out defaults so links stay short. */
export function writeLogUrlState(state: LogUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.projectId !== null) params.set(URL_PARAM_PROJECT, state.projectId);
  writeRange(state.range, params);
  if (state.filters.length > 0) params.set(URL_PARAM_FILTERS, JSON.stringify(state.filters));
  if (state.combine === "or") params.set(URL_PARAM_COMBINE, state.combine);
  if (state.query !== "") params.set(URL_PARAM_QUERY, state.query);
  if (state.queryMode) params.set(URL_PARAM_MODE, MODE_QUERY);
  return params;
}
