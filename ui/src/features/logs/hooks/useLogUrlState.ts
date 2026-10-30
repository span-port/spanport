// Read and change the explorer's filters, which live in the URL.
import { useSearchParams } from "react-router";

import { readLogUrlState, writeLogUrlState, type LogUrlState } from "../../../lib/logUrlState";

/**
 * The explorer state from the URL, and a function that changes part of it.
 *
 * Each change is a new history entry, so Back undoes the last filter change.
 */
export function useLogUrlState() {
  const [params, setParams] = useSearchParams();
  const state = readLogUrlState(params);
  const update = (change: Partial<LogUrlState>) => {
    setParams(writeLogUrlState({ ...state, ...change }));
  };
  return { state, update };
}
