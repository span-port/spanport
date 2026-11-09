import { LOG_RANGE_RULES } from "../../constants/logs";
import { timeZoneChoices } from "../../lib/formatTime";
import { rangeName, type RangeRules, type RangeSelection } from "../../lib/timeRange";

interface TimeRangePickerProps {
  range: RangeSelection;
  timeZone: string;
  customOpen: boolean;
  onSelectRange: (range: RangeSelection) => void;
  onSelectTimeZone: (timeZone: string) => void;
  onToggleCustom: () => void;
  /** The screen's quick ranges and how long its data is kept; Logs' by default. */
  rules?: RangeRules;
}

/** Quick ranges as buttons, a Custom button for anything else, and the timezone. */
export function TimeRangePicker({ rules = LOG_RANGE_RULES, ...props }: TimeRangePickerProps) {
  const { range, timeZone } = props;
  const custom = range.kind !== "preset";
  return (
    <div className="range-picker">
      <div className="range-picker-meta">
        <span>Time range · {rules.keptNote}</span>
        <label className="range-zone">
          Timezone
          <select
            className="input input-small"
            value={timeZone}
            onChange={(event) => {
              props.onSelectTimeZone(event.target.value);
            }}
          >
            {timeZoneChoices(new Date()).map((choice) => (
              <option key={choice.zone} value={choice.zone}>
                {choice.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div role="group" aria-label="Time range" className="segmented">
        {rules.presets.map((preset) => (
          <button
            key={preset.key}
            type="button"
            className="segment"
            aria-pressed={range.kind === "preset" && range.key === preset.key}
            title={preset.name}
            onClick={() => {
              props.onSelectRange({ kind: "preset", key: preset.key });
            }}
          >
            {preset.label}
          </button>
        ))}
        <button
          type="button"
          className="segment"
          aria-pressed={custom}
          aria-expanded={props.customOpen}
          onClick={props.onToggleCustom}
        >
          {custom ? rangeName(range, timeZone, rules) : "Custom"} ▾
        </button>
      </div>
    </div>
  );
}
