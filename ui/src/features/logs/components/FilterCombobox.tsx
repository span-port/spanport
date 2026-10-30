import type { FilterStage } from "../../../lib/filterSuggestions";
import { useFilterCombobox } from "../hooks/useFilterCombobox";
import type { FilterChip, LogItem } from "../types";

interface FilterComboboxProps {
  rows: LogItem[];
  onAddFilter: (chip: FilterChip) => void;
  onRemoveLast: () => void;
}

/** One box that builds a chip step by step: property, operator, value. */
export function FilterCombobox({ rows, onAddFilter, onRemoveLast }: FilterComboboxProps) {
  const box = useFilterCombobox(rows, onAddFilter, onRemoveLast);
  return (
    <div className="combobox">
      <label htmlFor="log-filter" className="field-label">
        Filter logs: pick a property, then a condition and a value, or just type to search messages
      </label>
      <div className="combobox-box" data-open={box.open}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="icon-muted">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4-4" />
        </svg>
        {box.prefix && <span className="combobox-prefix">{box.prefix}</span>}
        <input
          id="log-filter"
          type="text"
          role="combobox"
          aria-expanded={box.open}
          aria-controls="log-filter-options"
          autoComplete="off"
          className="combobox-input"
          value={box.typed}
          placeholder={placeholder(box.stage)}
          onChange={(event) => {
            box.onChange(event.target.value);
          }}
          onFocus={box.onFocus}
          onBlur={box.onBlur}
          onKeyDown={box.onKeyDown}
        />
      </div>
      {box.open && (
        <div id="log-filter-options" role="listbox" className="combobox-list">
          <div className="combobox-title">{box.title}</div>
          {box.items.map((item) => (
            <button
              key={`${item.label}${item.detail}`}
              type="button"
              role="option"
              aria-selected="false"
              className="combobox-option"
              // Keep focus in the input, so choosing doesn't close the list first.
              onMouseDown={(event) => {
                event.preventDefault();
              }}
              onClick={() => {
                box.choose(item.choice);
              }}
            >
              <span>{item.label}</span>
              <span className="combobox-detail">{item.detail}</span>
            </button>
          ))}
          {box.items.length === 0 && <div className="combobox-empty">Type a value and press Enter.</div>}
        </div>
      )}
    </div>
  );
}

function placeholder(stage: FilterStage): string {
  switch (stage.step) {
    case "property":
      return "Filter by property, or type text to search the message";
    case "operator":
      return "Choose an operator";
    case "value":
      return "Type or choose a value";
  }
}
