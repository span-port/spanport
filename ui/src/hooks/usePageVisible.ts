// Whether the browser tab is visible, so live updates can pause while it's hidden.
import { useSyncExternalStore } from "react";

import { VISIBILITY_EVENT } from "../constants/ui";

function subscribe(onChange: () => void): () => void {
  document.addEventListener(VISIBILITY_EVENT, onChange);
  return () => {
    document.removeEventListener(VISIBILITY_EVENT, onChange);
  };
}

function isVisible(): boolean {
  return document.visibilityState === "visible";
}

/** True while the tab is visible; re-renders when that changes. */
export function usePageVisible(): boolean {
  return useSyncExternalStore(subscribe, isVisible);
}
