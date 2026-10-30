import { useState } from "react";

import { NUMBER_LOCALE } from "../../../constants/ui";
import { groupChips, groupVerb } from "../../../lib/chipGroups";
import { propertyLabel } from "../../../lib/filterSuggestions";
import { chipsToQueryText } from "../../../lib/queryText";
import { useQueryForm } from "../hooks/useQueryForm";
import type { FilterChip, LogItem } from "../types";
import { FilterCombobox } from "./FilterCombobox";

interface FilterBarProps {
  rows: LogItem[];
  filters: FilterChip[];
  query: string;
  queryMode: boolean;
  /** Lines matching in the range, for the query line; undefined while counting. */
  matchCount: number | undefined;
  onAddFilter: (chip: FilterChip) => void;
  onRemoveFilter: (index: number) => void;
  onRemoveLast: () => void;
  onClearFilters: () => void;
  onApplyQuery: (query: string) => void;
  onSwitchToQuery: () => void;
  onSwitchToChips: () => void;
}

const numberFormat = new Intl.NumberFormat(NUMBER_LOCALE);

/**
 * The filter box and the filters in use (levels are on the cards above), or the advanced text
 * query. With filters, the query they run as is behind "Show query"; in query mode the query is
 * already on screen.
 */
export function FilterBar(props: FilterBarProps) {
  const [queryShown, setQueryShown] = useState(false);
  if (props.queryMode) {
    return (
      <div className="filter-panel">
        <QueryBox {...props} />
      </div>
    );
  }
  const runsAs = chipsToQueryText(props.filters);
  return (
    <div className="filter-panel">
      <ChipFilters {...props} />
      {runsAs && (
        <p className="runs-as">
          <button
            type="button"
            className="link-button link-muted"
            aria-expanded={queryShown}
            onClick={() => {
              setQueryShown(!queryShown);
            }}
          >
            {queryShown ? "Hide query" : "Show query"}
          </button>
          {queryShown && (
            <>
              <code className="code-inline">{runsAs}</code>
              {props.matchCount !== undefined &&
                ` · ${numberFormat.format(props.matchCount)} matching lines in range`}
            </>
          )}
        </p>
      )}
    </div>
  );
}

/** The filter box, and each property's filter as one chip ("Service is one of: api, worker"). */
function ChipFilters(props: FilterBarProps) {
  const groups = groupChips(props.filters);
  return (
    <>
      <div className="filter-box-row">
        <FilterCombobox rows={props.rows} onAddFilter={props.onAddFilter} onRemoveLast={props.onRemoveLast} />
        <button type="button" className="link-button link-muted" onClick={props.onSwitchToQuery}>
          Type a query instead
        </button>
      </div>
      {groups.length > 0 && (
        <div className="filter-row">
          {groups.map((group) => (
            <span key={`${group.field}${group.operator}`} className="chip">
              <span>
                {propertyLabel(group.field)} {groupVerb(group.operator, group.values.length)}
              </span>
              {group.values.map(({ value, index }) => (
                <span key={index} className="chip-value">
                  {value}
                  <button
                    type="button"
                    className="chip-remove"
                    aria-label={`Remove filter ${propertyLabel(group.field)} ${group.operator} ${value}`}
                    onClick={() => {
                      props.onRemoveFilter(index);
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </span>
          ))}
          <button type="button" className="link-button" onClick={props.onClearFilters}>
            Clear filters
          </button>
        </div>
      )}
    </>
  );
}

/** The advanced text query; Enter runs it. */
function QueryBox(props: FilterBarProps) {
  const form = useQueryForm(props.query, props.onApplyQuery);
  return (
    <form className="query-box" onSubmit={(event) => void form.submit(event)}>
      <label className="field">
        <span className="field-label">
          Query · AND, OR, NOT or -word, &quot;exact phrase&quot;, field:value, ( ) and * wildcards. Press
          Enter to run.
        </span>
        <input
          type="search"
          className="input mono"
          placeholder="e.g. level:ERROR AND (timeout OR deadlock) -healthcheck"
          {...form.register("query")}
        />
      </label>
      {form.error && (
        <p role="alert" className="field-error">
          {form.error}
        </p>
      )}
      <div className="query-actions">
        <button type="button" className="link-button" onClick={props.onSwitchToChips}>
          ← Back to filters
        </button>
        {props.matchCount !== undefined && (
          <span className="text-muted text-xs">
            {numberFormat.format(props.matchCount)} matching lines in range
          </span>
        )}
      </div>
    </form>
  );
}
