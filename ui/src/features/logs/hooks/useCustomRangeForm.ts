// The custom time range dialog: absolute start and end in the chosen zone, or "last N units".
import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type BaseSyntheticEvent } from "react";
import { useForm, useWatch } from "react-hook-form";
import * as zod from "zod";

import {
  CUSTOM_RANGE_START_MINUTES,
  DEFAULT_RELATIVE_AMOUNT,
  DEFAULT_RELATIVE_UNIT,
  MAX_RANGE_MINUTES,
  RELATIVE_UNITS,
} from "../../../constants/logs";
import { HOURS_MINUTES_LENGTH, MS_PER_MINUTE } from "../../../constants/ui";
import { utcToZonedInputs, zonedInputsToUtc } from "../../../lib/formatTime";
import { rangeProblem, type RangeSelection } from "../../../lib/timeRange";

const unitValues = RELATIVE_UNITS.map((choice) => choice.unit) as [
  (typeof RELATIVE_UNITS)[number]["unit"],
  ...(typeof RELATIVE_UNITS)[number]["unit"][],
];

const customRangeSchema = zod.object({
  kind: zod.enum(["absolute", "relative"]),
  startDate: zod.string(),
  startTime: zod.string(),
  endDate: zod.string(),
  endTime: zod.string(),
  amount: zod.coerce.number<string>(),
  unit: zod.enum(unitValues),
});
type CustomRangeInput = zod.input<typeof customRangeSchema>;
type CustomRangeValues = zod.output<typeof customRangeSchema>;

/** The range the form describes; absolute times are read in `timeZone`. */
function toRange(values: CustomRangeValues, timeZone: string): RangeSelection {
  if (values.kind === "relative") return { kind: "relative", amount: values.amount, unit: values.unit };
  return {
    kind: "absolute",
    startMs: zonedInputsToUtc(values.startDate, values.startTime, timeZone),
    endMs: zonedInputsToUtc(values.endDate, values.endTime, timeZone),
  };
}

/** Starting values: the current custom range, or the last hour. */
function initialValues(range: RangeSelection, timeZone: string, nowMs: number): CustomRangeInput {
  const startMs =
    range.kind === "absolute" ? range.startMs : nowMs - CUSTOM_RANGE_START_MINUTES * MS_PER_MINUTE;
  const endMs = range.kind === "absolute" ? range.endMs : nowMs;
  const start = utcToZonedInputs(startMs, timeZone);
  const end = utcToZonedInputs(endMs, timeZone);
  return {
    kind: range.kind === "relative" ? "relative" : "absolute",
    startDate: start.date,
    startTime: start.time.slice(0, HOURS_MINUTES_LENGTH),
    endDate: end.date,
    endTime: end.time.slice(0, HOURS_MINUTES_LENGTH),
    amount: String(range.kind === "relative" ? range.amount : DEFAULT_RELATIVE_AMOUNT),
    unit: range.kind === "relative" ? range.unit : DEFAULT_RELATIVE_UNIT,
  };
}

/**
 * Form state for the custom range dialog.
 *
 * @param onApply - Called with a valid range; problems (end before start, older than 7 days)
 *   are shown instead.
 */
export function useCustomRangeForm(
  range: RangeSelection,
  timeZone: string,
  onApply: (range: RangeSelection) => void,
) {
  const [openedAtMs] = useState(Date.now);
  const form = useForm<CustomRangeInput, unknown, CustomRangeValues>({
    resolver: zodResolver(customRangeSchema),
    defaultValues: initialValues(range, timeZone, openedAtMs),
  });
  const kind = useWatch({ control: form.control, name: "kind" });
  // Built when the form is submitted, so "now" is the moment of submitting.
  const submit = (event?: BaseSyntheticEvent) =>
    form.handleSubmit((values) => {
      const chosen = toRange(values, timeZone);
      const problem = rangeProblem(chosen, Date.now());
      if (problem) form.setError("root", { message: problem });
      else onApply(chosen);
    })(event);
  // The pickers offer days from 7 days ago (retention) to today, in the chosen zone.
  const today = utcToZonedInputs(openedAtMs, timeZone).date;
  const earliestDay = utcToZonedInputs(openedAtMs - MAX_RANGE_MINUTES * MS_PER_MINUTE, timeZone).date;
  return {
    register: form.register,
    control: form.control,
    today,
    earliestDay,
    setKind: (next: "absolute" | "relative") => {
      form.setValue("kind", next);
    },
    kind,
    submit,
    problem: form.formState.errors.root?.message ?? null,
  };
}
