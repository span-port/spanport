import { useState } from "react";
import { Link } from "react-router";

import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { TRUNCATED_TRACE_NOTE, WATERFALL_INDENT_PX } from "../../../constants/traces";
import { REQUESTS_ROUTE } from "../../../constants/ui";
import { formatRangeTime } from "../../../lib/formatTime";
import { barPosition, formatDuration, labelName, spanFailed, type WaterfallRow } from "../../../lib/waterfall";
import { useSessionStore } from "../../../state/sessionStore";
import { useTrace } from "../hooks/useTrace";

/** One request as a waterfall: every step, nested, with where the time went. */
export function TracePage() {
  const trace = useTrace();
  const timeZone = useSessionStore((session) => session.timeZone);
  const { detail } = trace;
  return (
    <div className="setup-page">
      <header className="page-heading page-heading-row">
        <div>
          <Link to={REQUESTS_ROUTE} className="link-button">
            ← Requests
          </Link>
          <h1 className="page-title">{detail?.spans[0]?.name ?? "Request"}</h1>
          {detail && (
            <p className="text-secondary">
              {formatDuration(detail.duration_ms)} · {detail.spans.length} steps · started{" "}
              {formatRangeTime(Date.parse(detail.start_ts), timeZone)} · trace{" "}
              <span className="mono">{detail.trace_id}</span>
            </p>
          )}
        </div>
        {trace.logsLink && (
          <Link className="button button-secondary" to={trace.logsLink}>
            See logs
          </Link>
        )}
      </header>
      {trace.error && <ErrorBanner error={trace.error} />}
      {detail?.truncated && (
        <p className="banner banner-warning">{TRUNCATED_TRACE_NOTE}</p>
      )}
      {detail && (
        <section className="panel panel-table waterfall" aria-label="Waterfall">
          <div className="waterfall-head" aria-hidden="true">
            <span>Step</span>
            <span>Own time</span>
            <span>Timeline</span>
          </div>
          {trace.rows.map((row) => (
            <WaterfallLine key={row.span.span_id} row={row} totalMs={detail.duration_ms} />
          ))}
        </section>
      )}
    </div>
  );
}

/** One step: its name and label, own time, and its bar on the trace's timeline. Click for details. */
function WaterfallLine({ row, totalMs }: { row: WaterfallRow; totalMs: number }) {
  const [open, setOpen] = useState(false);
  const { span, depth } = row;
  const bar = barPosition(span, totalMs);
  const failed = spanFailed(span);
  return (
    <>
      <button
        type="button"
        className="waterfall-row"
        aria-expanded={open}
        data-error={failed}
        onClick={() => {
          setOpen(!open);
        }}
      >
        <span className="waterfall-name" style={{ paddingLeft: depth * WATERFALL_INDENT_PX }}>
          <span className={`span-label span-label-${span.label}`}>{labelName(span.label)}</span>
          <span className="truncate">{span.name}</span>
        </span>
        <span className="mono text-sm" title="Own time: not spent in the steps below this one">
          {formatDuration(span.self_ms)}
        </span>
        <span className="waterfall-track">
          <span
            className={`waterfall-bar span-bar-${span.label}`}
            style={{ marginLeft: `${String(bar.left)}%`, width: `${String(bar.width)}%` }}
          />
          <span className="mono text-xs waterfall-duration">{formatDuration(span.duration_ms)}</span>
        </span>
      </button>
      {open && (
        <dl className="waterfall-details">
          <dt>Service</dt>
          <dd>{span.service}</dd>
          {span.status_message && (
            <>
              <dt>Error</dt>
              <dd>{span.status_message}</dd>
            </>
          )}
          {Object.entries(span.attributes).map(([key, value]) => (
            <AttributeRow key={key} name={key} value={value} />
          ))}
        </dl>
      )}
    </>
  );
}

/** One attribute of a span, as a term and its value. */
function AttributeRow({ name, value }: { name: string; value: string }) {
  return (
    <>
      <dt className="mono">{name}</dt>
      <dd className="mono">{value}</dd>
    </>
  );
}
