import { WEEKDAY_LABELS } from "../../constants/ui";
import { useDatePicker } from "../../hooks/useDatePicker";
import { dayLabel, monthGrid, monthTitle } from "../../lib/calendar";

interface DatePickerProps {
  /** "YYYY-MM-DD". */
  value: string;
  onChange: (date: string) => void;
  /** Earliest and latest days that can be picked ("YYYY-MM-DD"). */
  min: string;
  max: string;
  /** Names the field for screen readers, e.g. "Start date". */
  label: string;
  /** Today in the chosen timezone, marked in the grid. */
  today: string;
}

/** A date field in the app's style: the day as text, and a month grid when opened. */
export function DatePicker({ value, onChange, min, max, label, today }: DatePickerProps) {
  const picker = useDatePicker(value);
  return (
    <div className="date-picker">
      <button
        type="button"
        className="input date-picker-button"
        aria-label={`${label}: ${dayLabel(value)}`}
        aria-expanded={picker.open}
        onClick={picker.toggle}
      >
        <span>{dayLabel(value)}</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="icon-muted">
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M3 10h18M8 3v4M16 3v4" />
        </svg>
      </button>
      {picker.open && (
        <div
          className="date-picker-popover"
          role="dialog"
          aria-label={label}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              picker.close();
            }
          }}
        >
          <div className="date-picker-header">
            <button type="button" className="date-picker-nav" aria-label="Previous month" onClick={picker.previousMonth}>
              ‹
            </button>
            <span className="date-picker-title">{monthTitle(picker.shownMonth)}</span>
            <button type="button" className="date-picker-nav" aria-label="Next month" onClick={picker.nextMonth}>
              ›
            </button>
          </div>
          <div className="date-picker-grid">
            {WEEKDAY_LABELS.map((weekday) => (
              <span key={weekday} className="date-picker-weekday">
                {weekday}
              </span>
            ))}
            {monthGrid(picker.shownMonth).map((day) => (
              <button
                key={day.date}
                type="button"
                className="date-picker-day"
                data-outside={!day.inMonth}
                data-today={day.date === today}
                aria-pressed={day.date === value}
                aria-label={dayLabel(day.date)}
                disabled={day.date < min || day.date > max}
                onClick={() => {
                  onChange(day.date);
                  picker.close();
                }}
              >
                {day.dayOfMonth}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
