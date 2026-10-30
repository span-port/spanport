// Open state and the month shown by a date picker.
import { useState } from "react";

import { addMonths, monthOf } from "../lib/calendar";

/** The popover's open state and the month on show; opening jumps back to the chosen day's month. */
export function useDatePicker(value: string) {
  const [open, setOpen] = useState(false);
  const [shownMonth, setShownMonth] = useState(monthOf(value));
  return {
    open,
    shownMonth,
    toggle: () => {
      setShownMonth(monthOf(value));
      setOpen(!open);
    },
    close: () => {
      setOpen(false);
    },
    previousMonth: () => {
      setShownMonth(addMonths(shownMonth, -1));
    },
    nextMonth: () => {
      setShownMonth(addMonths(shownMonth, 1));
    },
  };
}
