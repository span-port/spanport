import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";

import {
  LOAD_MORE_WITHIN_ROWS,
  LOG_ROW_HEIGHT_PX,
  LOG_ROWS_OVERSCAN,
} from "../../../constants/logs";
import type { FilterChip, LogItem } from "../types";
import { LogRow } from "./LogRow";

interface LogTableProps {
  rows: LogItem[];
  timeZone: string;
  expandedLogId: string | null;
  onToggle: (logId: string) => void;
  /** Adds a filter chip from a field of an expanded line. */
  onFilter: (chip: FilterChip) => void;
  /** Called while the user scrolls near the end, to load the next page. */
  onNearEnd: () => void;
  footer: string | null;
}

/** The log lines, newest first. Only visible rows are rendered; expanded rows are measured. */
export function LogTable(props: LogTableProps) {
  const { rows, timeZone, expandedLogId, onToggle, onFilter, onNearEnd, footer } = props;
  const scrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => LOG_ROW_HEIGHT_PX,
    overscan: LOG_ROWS_OVERSCAN,
    getItemKey: (index) => rows[index]?.log_id ?? index,
    onChange: (instance) => {
      const lastVisible = instance.getVirtualItems().at(-1);
      if (lastVisible && lastVisible.index >= rows.length - LOAD_MORE_WITHIN_ROWS) onNearEnd();
    },
  });
  // No line has a trace yet (most apps until tracing is set up): give its width to the message.
  const hasTrace = rows.some((row) => row.trace_id !== "");
  return (
    <div ref={scrollRef} className="log-scroll">
      <div className="log-table" data-trace={hasTrace}>
        <div className="log-grid log-header" aria-hidden="true">
          <span>Time</span>
          <span>Level</span>
          <span>Service</span>
          <span>Message</span>
          <span className="trace-cell">Trace</span>
        </div>
        <div className="log-rows" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((item) => {
            const log = rows[item.index];
            if (!log) return null;
            return (
              <div
                key={item.key}
                ref={virtualizer.measureElement}
                data-index={item.index}
                className="log-slot"
                style={{ transform: `translateY(${item.start}px)` }}
              >
                <LogRow
                  log={log}
                  timeZone={timeZone}
                  expanded={log.log_id === expandedLogId}
                  onToggle={() => {
                    onToggle(log.log_id);
                  }}
                  onFilter={onFilter}
                />
              </div>
            );
          })}
        </div>
        {footer && <p className="log-footer">{footer}</p>}
      </div>
    </div>
  );
}
