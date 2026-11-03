// What the waterfall shows: which steps are collapsed and which one is selected.
import { useState } from "react";

import { visibleRows, type WaterfallRow } from "../../../lib/waterfall";

/**
 * Collapse and select steps of a trace's waterfall.
 *
 * @param rows - Every step, in tree order.
 * @returns The rows to show, the selected step (the request itself until one is clicked), and
 *   `select`, `toggle` and `isCollapsed`.
 */
export function useWaterfall(rows: WaterfallRow[]) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = rows.find((row) => row.span.span_id === selectedId) ?? rows[0] ?? null;
  return {
    shown: visibleRows(rows, collapsed),
    selected,
    select: (spanId: string) => {
      setSelectedId(spanId);
    },
    isCollapsed: (spanId: string) => collapsed.has(spanId),
    toggle: (spanId: string) => {
      setCollapsed((current) => {
        const next = new Set(current);
        if (!next.delete(spanId)) next.add(spanId);
        return next;
      });
    },
  };
}
