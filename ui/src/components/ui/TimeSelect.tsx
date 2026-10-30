import { HOURS_IN_DAY, MINUTES_IN_HOUR } from "../../constants/ui";

interface TimeSelectProps {
  /** "HH:MM", 24-hour. */
  value: string;
  onChange: (time: string) => void;
  /** Names the field, e.g. "Start time". */
  label: string;
}

const twoDigits = (number: number) => String(number).padStart(2, "0");
const HOURS = Array.from({ length: HOURS_IN_DAY }, (_unused, hour) => twoDigits(hour));
const MINUTES = Array.from({ length: MINUTES_IN_HOUR }, (_unused, minute) => twoDigits(minute));

/** A time as two styled dropdowns, hour and minute (24-hour, no AM/PM to misread). */
export function TimeSelect({ value, onChange, label }: TimeSelectProps) {
  const [hour = "00", minute = "00"] = value.split(":");
  return (
    <span className="time-select" role="group" aria-label={label}>
      <select
        className="input"
        aria-label={`${label} hour`}
        value={hour}
        onChange={(event) => {
          onChange(`${event.target.value}:${minute}`);
        }}
      >
        {HOURS.map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </select>
      <span className="time-select-separator" aria-hidden="true">
        :
      </span>
      <select
        className="input"
        aria-label={`${label} minute`}
        value={minute}
        onChange={(event) => {
          onChange(`${hour}:${event.target.value}`);
        }}
      >
        {MINUTES.map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </select>
    </span>
  );
}
