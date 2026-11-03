import { Link } from "react-router";

import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { StatCard } from "../../../components/ui/StatCard";
import { STEP_KINDS, TRUNCATED_TRACE_NOTE } from "../../../constants/traces";
import { REQUESTS_ROUTE } from "../../../constants/ui";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatDuration, spanFailed, stepKindName } from "../../../lib/waterfall";
import { useSessionStore } from "../../../state/sessionStore";
import { useTrace } from "../hooks/useTrace";
import { useWaterfall } from "../hooks/useWaterfall";
import { SpanDetails } from "./SpanDetails";
import { Waterfall } from "./Waterfall";

/** One request: where its time went, every step on a timeline, and the chosen step's details. */
export function TracePage() {
  const trace = useTrace();
  const waterfall = useWaterfall(trace.rows);
  const timeZone = useSessionStore((session) => session.timeZone);
  const { detail, times } = trace;
  const root = trace.rows[0]?.span;
  return (
    <div className="setup-page">
      <Link to={REQUESTS_ROUTE} className="back-link">
        ← Requests
      </Link>
      <header className="page-heading page-heading-row">
        <div className="trace-title">
          <div className="trace-title-line">
            <h1 className="page-title mono">{root?.name ?? "Request"}</h1>
            {root && root.http_status > 0 && (
              <span className="status-pill" data-error={spanFailed(root)}>
                {root.http_status}
              </span>
            )}
          </div>
          {detail && root && (
            <p className="text-secondary">
              {formatRangeTime(Date.parse(detail.start_ts), timeZone)} · {root.service} · {detail.spans.length} steps ·
              trace <span className="mono">{detail.trace_id}</span>
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
      {detail?.truncated && <p className="banner banner-warning">{TRUNCATED_TRACE_NOTE}</p>}
      {detail && times && (
        <div className="stat-cards">
          <StatCard label="Total" value={formatDuration(detail.duration_ms)} />
          {STEP_KINDS.map((kind) => (
            <StatCard key={kind} label={stepKindName(kind)} value={formatDuration(times[kind])} swatch={kind} />
          ))}
        </div>
      )}
      {detail && waterfall.selected && (
        <div className="trace-layout">
          <Waterfall
            traceId={detail.trace_id}
            totalMs={detail.duration_ms}
            rows={waterfall.shown}
            selectedId={waterfall.selected.span.span_id}
            onSelect={waterfall.select}
            onToggle={waterfall.toggle}
            isCollapsed={waterfall.isCollapsed}
          />
          <SpanDetails span={waterfall.selected.span} />
        </div>
      )}
    </div>
  );
}
