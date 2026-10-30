import { TIME_PRESETS } from "../../../constants/logs";
import { timeZoneChoices } from "../../../lib/formatTime";
import { rangeName, type RangeSelection } from "../../../lib/timeRange";

interface TimeRangePickerProps {
  range: RangeSelection;
  timeZone: string;
  customOpen: boolean;
  onSelectRange: (range: RangeSelection) => void;
  onSelectTimeZone: (timeZone: string) => void;
  onToggleCustom: () => void;
}

/** Quick ranges as buttons, a Custom button for anything else, and the timezone. */
export function TimeRangePicker(props: TimeRangePickerProps) {
  const { range, timeZone } = props;
  const custom = range.kind !== "preset";
  return (
    <div className="range-picker">
      <div className="range-picker-meta">
        <span>Time range · logs kept 7 days</span>
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
        {TIME_PRESETS.map((preset) => (
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
          {custom ? rangeName(range, timeZone) : "Custom"} ▾
        </button>
      </div>
    </div>
  );
}
