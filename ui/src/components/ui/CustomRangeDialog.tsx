import { Fragment } from "react";
import { Controller } from "react-hook-form";

import { LOG_RANGE_RULES, RELATIVE_UNITS } from "../../constants/logs";
import { useCustomRangeForm } from "../../hooks/useCustomRangeForm";
import type { RangeRules, RangeSelection } from "../../lib/timeRange";
import { Button } from "./Button";
import { DatePicker } from "./DatePicker";
import { TimeSelect } from "./TimeSelect";

interface CustomRangeDialogProps {
  range: RangeSelection;
  timeZone: string;
  onApply: (range: RangeSelection) => void;
  onCancel: () => void;
  /** How far back the screen's data goes; Logs' by default. */
  rules?: RangeRules;
}

/** Fixed start and end times (read in the chosen timezone), or "last N minutes / hours / days". */
export function CustomRangeDialog({ range, timeZone, onApply, onCancel, rules = LOG_RANGE_RULES }: CustomRangeDialogProps) {
  const form = useCustomRangeForm(range, timeZone, onApply, rules);
  return (
    <form
      role="dialog"
      aria-label="Custom time range"
      className="dialog dialog-popover"
      noValidate
      onSubmit={(event) => void form.submit(event)}
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel();
      }}
    >
      <h2 className="section-title">Custom time range</h2>
      <div className="tabs">
        <button
          type="button"
          className="tab"
          aria-pressed={form.kind === "absolute"}
          onClick={() => {
            form.setKind("absolute");
          }}
        >
          Absolute
        </button>
        <button
          type="button"
          className="tab"
          aria-pressed={form.kind === "relative"}
          onClick={() => {
            form.setKind("relative");
          }}
        >
          Relative
        </button>
      </div>
      {form.kind === "absolute" ? (
        <div className="dialog-grid">
          {(
            [
              ["startDate", "startTime", "Start"],
              ["endDate", "endTime", "End"],
            ] as const
          ).map(([dateField, timeField, edge]) => (
            <Fragment key={edge}>
              <div className="field">
                <span className="field-label">{edge} date</span>
                <Controller
                  control={form.control}
                  name={dateField}
                  render={({ field }) => (
                    <DatePicker
                      label={`${edge} date`}
                      value={field.value}
                      onChange={field.onChange}
                      min={form.earliestDay}
                      max={form.today}
                      today={form.today}
                    />
                  )}
                />
              </div>
              <div className="field">
                <span className="field-label">{edge} time</span>
                <Controller
                  control={form.control}
                  name={timeField}
                  render={({ field }) => (
                    <TimeSelect label={`${edge} time`} value={field.value} onChange={field.onChange} />
                  )}
                />
              </div>
            </Fragment>
          ))}
        </div>
      ) : (
        <div className="dialog-relative">
          <span>Last</span>
          <label className="field">
            <span className="field-label">Amount</span>
            <input type="number" min="1" className="input input-amount" {...form.register("amount")} />
          </label>
          <label className="field">
            <span className="field-label">Unit</span>
            <select className="input" {...form.register("unit")}>
              {RELATIVE_UNITS.map((choice) => (
                <option key={choice.unit} value={choice.unit}>
                  {choice.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      <p className="text-muted text-sm">
        Times are read in {timeZone}; {rules.keptNote}.
      </p>
      {form.problem && (
        <p role="alert" className="field-error">
          {form.problem}
        </p>
      )}
      <div className="dialog-actions">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="primary" type="submit">
          Apply
        </Button>
      </div>
    </form>
  );
}
