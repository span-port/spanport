// Shapes of the server's log search API (see server schemas/log_search.py).

export type FilterOperator = "=" | "!=" | ":" | "!:";
export type FilterCombine = "and" | "or";

export interface FilterChip {
  field: string;
  operator: FilterOperator;
  value: string;
}

export interface LogTailRequest {
  project_id: string;
  filters: FilterChip[];
  combine: FilterCombine;
  query: string;
}

export interface LogFilterRequest extends LogTailRequest {
  start: string;
  end: string;
}

export interface LogItem {
  log_id: string;
  ts: string;
  service: string;
  level: string;
  message: string;
  trace_id: string;
  span_id: string;
  attributes: Record<string, string>;
}

export interface LogSearchResponse {
  data: LogItem[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface LogCountsResponse {
  total: number;
  by_level: Record<string, number>;
}
