// The filter box: pick a property, an operator and a value, or type text to search messages.
import { useState, type KeyboardEvent } from "react";

import {
  enterChoice,
  filterSuggestions,
  stagePrefix,
  type FilterChoice,
  type FilterStage,
} from "../../../lib/filterSuggestions";
import type { FilterChip, LogItem } from "../types";

const START: FilterStage = { step: "property" };

/**
 * State and handlers for the filter combobox.
 *
 * Enter adds the typed text, Escape starts over, and Backspace in an empty box steps back
 * (or removes the last chip when nothing is being built).
 *
 * @param rows - Logs on screen, for value suggestions.
 * @param onAddFilter - Called with each finished chip.
 * @param onRemoveLast - Called when Backspace should remove the last chip.
 */
export function useFilterCombobox(
  rows: LogItem[],
  onAddFilter: (chip: FilterChip) => void,
  onRemoveLast: () => void,
) {
  const [stage, setStage] = useState<FilterStage>(START);
  const [typed, setTyped] = useState("");
  const [open, setOpen] = useState(false);

  const choose = (choice: FilterChoice) => {
    setTyped("");
    if (choice.action === "property") {
      setStage({ step: "operator", field: choice.field });
    } else if (choice.action === "operator" && stage.step === "operator") {
      setStage({ step: "value", field: stage.field, operator: choice.operator });
    } else if (choice.action === "chip") {
      onAddFilter(choice.chip);
      setStage(START);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const choice = enterChoice(stage, typed);
      if (choice) choose(choice);
    } else if (event.key === "Escape") {
      setStage(START);
      setTyped("");
      setOpen(false);
    } else if (event.key === "Backspace" && typed === "") {
      if (stage.step === "property") onRemoveLast();
      else setStage(START);
    }
  };

  const dropdown = filterSuggestions(stage, typed, rows);
  return {
    typed,
    open,
    stage,
    prefix: stagePrefix(stage),
    title: dropdown.title,
    items: dropdown.items,
    choose,
    onKeyDown,
    onChange: (value: string) => {
      setTyped(value);
      setOpen(true);
    },
    onFocus: () => {
      setOpen(true);
    },
    onBlur: () => {
      setOpen(false);
    },
  };
}
