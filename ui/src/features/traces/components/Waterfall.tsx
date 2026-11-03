import type { CSSProperties } from "react";

import { MAX_STAGGERED_ROWS, WATERFALL_INDENT_PX } from "../../../constants/traces";
import {
  axisTicks,
  barPosition,
  formatDuration,
  labelName,
  spanFailed,
  stepKindOf,
  type WaterfallRow,
} from "../../../lib/waterfall";

interface WaterfallProps {
  /** A new trace replays the bars' entrance. */
  traceId: string;
  totalMs: number;
  rows: WaterfallRow[];
  selectedId: string;
  onSelect: (spanId: string) => void;
  onToggle: (spanId: string) => void;
  isCollapsed: (spanId: string) => boolean;
}

/** Every step of a request on one timeline: nested names on the left, bars where they ran. */
export function Waterfall({ traceId, totalMs, rows, selectedId, onSelect, onToggle, isCollapsed }: WaterfallProps) {
  const ticks = axisTicks(totalMs);
  return (
    <section className="panel panel-table waterfall" aria-label="Waterfall" key={traceId}>
      <h2 className="waterfall-title">
        Steps in this request <span className="text-secondary text-sm">· click one for its details</span>
      </h2>
      <div className="waterfall-scroll">
        <div className="waterfall-grid waterfall-head" aria-hidden="true">
          <span>Step</span>
          <span className="waterfall-axis">
            {ticks.map((tick) => (
              <span key={tick.label} className="waterfall-tick" style={{ left: `${String(tick.percent)}%` }}>
                {tick.label}
              </span>
            ))}
          </span>
          <span className="waterfall-duration-head">Duration</span>
        </div>
        {rows.map((row, index) => (
          <WaterfallLine
            key={row.span.span_id}
            row={row}
            order={Math.min(index, MAX_STAGGERED_ROWS)}
            totalMs={totalMs}
            gridLines={ticks.map((tick) => tick.percent)}
            selected={row.span.span_id === selectedId}
            collapsed={isCollapsed(row.span.span_id)}
            onSelect={onSelect}
            onToggle={onToggle}
          />
        ))}
      </div>
    </section>
  );
}

interface WaterfallLineProps {
  row: WaterfallRow;
  /** Its place in the entrance: bars grow one after another. */
  order: number;
  totalMs: number;
  gridLines: number[];
  selected: boolean;
  collapsed: boolean;
  onSelect: (spanId: string) => void;
  onToggle: (spanId: string) => void;
}

/** One step: expand arrow, label and name, its bar on the timeline, and how long it took. */
function WaterfallLine({ row, order, totalMs, gridLines, selected, collapsed, onSelect, onToggle }: WaterfallLineProps) {
  const { span, depth, hasChildren } = row;
  const bar = barPosition(span, totalMs);
  const kind = stepKindOf(span.label);
  const select = () => {
    onSelect(span.span_id);
  };
  return (
    <div
      className="waterfall-grid waterfall-row"
      data-selected={selected}
      data-error={spanFailed(span)}
      style={{ "--row-order": order } as CSSProperties}
      onClick={select}
    >
      <span className="waterfall-name" style={{ paddingLeft: depth * WATERFALL_INDENT_PX }}>
        {hasChildren ? (
          <button
            type="button"
            className="waterfall-toggle"
            aria-expanded={!collapsed}
            aria-label={collapsed ? `Show the steps inside ${span.name}` : `Hide the steps inside ${span.name}`}
            onClick={(event) => {
              event.stopPropagation();
              onToggle(span.span_id);
            }}
          >
            {collapsed ? "▸" : "▾"}
          </button>
        ) : (
          <span className="waterfall-toggle-space" aria-hidden="true" />
        )}
        <button type="button" className="waterfall-step" aria-pressed={selected} onClick={select}>
          <span className={`span-label step-label-${kind}`}>{labelName(span.label)}</span>
          <span className="truncate mono">{span.name}</span>
        </button>
      </span>
      <span className="waterfall-track" aria-hidden="true">
        {gridLines.map((percent) => (
          <span key={percent} className="waterfall-gridline" style={{ left: `${String(percent)}%` }} />
        ))}
        <span
          className={`waterfall-bar step-${kind}`}
          style={{ left: `${String(bar.left)}%`, width: `${String(bar.width)}%` }}
        />
      </span>
      <span className="waterfall-duration mono">{formatDuration(span.duration_ms)}</span>
    </div>
  );
}
