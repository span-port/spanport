import { Link } from "react-router";

import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { StatCard } from "../../../components/ui/StatCard";
import { STEP_KINDS } from "../../../constants/traces";
import { errorRate, layerTimes, percentileExample, statusGroup, stepShares } from "../../../lib/endpoints";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatDuration, stepKindName, stepKindOf } from "../../../lib/waterfall";
import type { EndpointDetail, EndpointStats } from "../api";
import { useEndpointDetail } from "../hooks/useEndpointDetail";
import { RangeControls } from "./RangeControls";
import { TimelineChart } from "./TimelineChart";

/** One API in depth: its numbers, how they changed, its status codes, steps and slowest requests. */
export function ApiDetailPage() {
  const page = useEndpointDetail();
  const { detail, endpoint, range } = page;
  const timeZone = range.timeZone;
  return (
    <div className="setup-page">
      <Link to={page.backLink} className="back-link">
        ← APIs
      </Link>
      <header className="page-heading page-heading-row">
        <div className="trace-title">
          <h1 className="page-title mono">
            <span className="method-tag">{endpoint.http_method || "SPAN"}</span> {endpoint.route}
          </h1>
          <p className="text-secondary">
            {endpoint.service} · {range.name} ·{" "}
            <Link to={page.requestsLink}>See its requests</Link>
          </p>
        </div>
        <RangeControls range={range} />
      </header>
      {page.error && <ErrorBanner error={page.error} />}
      {detail && !detail.summary && <p className="panel empty-row text-secondary">No requests to this API in this range.</p>}
      {detail?.summary && (
        <>
          <SummaryCards summary={detail.summary} />
          <section className="panel" aria-label="Over time">
            <h2 className="panel-title">Over time</h2>
            <TimelineChart
              points={detail.timeline}
              start={range.start}
              end={range.end}
              bucketSeconds={detail.bucket_seconds}
              timeZone={timeZone}
            />
          </section>
          <div className="detail-columns">
            <WhereTimeGoes summary={detail.summary} />
            <StatusCodes detail={detail} />
          </div>
          <StepsTable detail={detail} />
          <section className="panel panel-table" aria-label="Slowest requests">
            <h2 className="panel-title table-heading">Slowest requests</h2>
            <table className="key-table request-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Status</th>
                  <th className="number">Duration</th>
                </tr>
              </thead>
              <tbody>
                {detail.slowest.map((request) => (
                  <tr
                    key={request.span_id}
                    className="clickable-row"
                    onClick={() => {
                      page.openTrace(request.trace_id);
                    }}
                  >
                    <td>
                      <Link
                        className="request-link mono"
                        to={page.traceLink(request.trace_id)}
                        onClick={(event) => {
                          event.stopPropagation();
                        }}
                      >
                        {formatRangeTime(Date.parse(request.start_ts), timeZone)}
                      </Link>
                    </td>
                    <td>
                      {request.http_status > 0 && (
                        <span className="status-pill" data-error={request.error}>
                          {request.http_status}
                        </span>
                      )}
                    </td>
                    <td className="number mono">{formatDuration(request.duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

/** Requests, error rate and the three speeds, with what they mean for this API. */
function SummaryCards({ summary }: { summary: EndpointStats }) {
  return (
    <>
      <div className="stat-cards">
        <StatCard label="Requests" value={summary.requests.toLocaleString("en")} />
        <StatCard label="Error rate" value={errorRate(summary.errors, summary.requests)} />
        <StatCard label="Typical (p50)" value={formatDuration(summary.p50_ms)} />
        <StatCard label="Slow 5% (p95)" value={formatDuration(summary.p95_ms)} />
        <StatCard label="Slowest 1% (p99)" value={formatDuration(summary.p99_ms)} />
      </div>
      <p className="text-secondary text-sm">{percentileExample(summary)}</p>
    </>
  );
}

/** An average request's time split into your code, database, external calls and LLM. */
function WhereTimeGoes({ summary }: { summary: EndpointStats }) {
  const times = layerTimes(summary.layers);
  const shares = stepShares(times);
  return (
    <section className="panel" aria-label="Where time goes">
      <h2 className="panel-title">Where an average request's {formatDuration(summary.avg_ms)} goes</h2>
      <div className="share-bar share-bar-large" aria-hidden="true">
        {shares.map((share) => (
          <span key={share.kind} className={`step-${share.kind}`} style={{ width: `${String(share.percent)}%` }} />
        ))}
      </div>
      <dl className="layer-list">
        {STEP_KINDS.map((kind) => (
          <div key={kind} className="layer-item">
            <dt>
              <span className={`swatch step-${kind}`} aria-hidden="true" />
              {stepKindName(kind)}
            </dt>
            <dd className="mono">{formatDuration(times[kind])}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** How many requests got each HTTP status. */
function StatusCodes({ detail }: { detail: EndpointDetail }) {
  return (
    <section className="panel" aria-label="Status codes">
      <h2 className="panel-title">Status codes</h2>
      <dl className="layer-list">
        {detail.statuses.map((item) => (
          <div key={item.status} className="layer-item">
            <dt>
              <span className="status-pill" data-error={item.status >= 500}>
                {item.status || "-"}
              </span>
              <span className="text-secondary text-sm">{statusGroup(item.status)}</span>
            </dt>
            <dd className="mono">{item.requests.toLocaleString("en")}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Every query, outgoing call, LLM call and method the API makes, most total time first. */
function StepsTable({ detail }: { detail: EndpointDetail }) {
  return (
    <section className="panel panel-table" aria-label="Steps inside this API">
      <div className="table-heading">
        <h2 className="panel-title">Steps inside this API</h2>
        <span className="text-muted text-xs">Most total time first. Calls per request above 1 can mean a query in a loop.</span>
      </div>
      <table className="key-table endpoint-table">
        <thead>
          <tr>
            <th>Step</th>
            <th className="number">Calls / request</th>
            <th className="number">Average</th>
            <th className="number">Slow 5%</th>
            <th className="number">Total</th>
          </tr>
        </thead>
        <tbody>
          {detail.steps.map((step) => {
            const kind = stepKindOf(step.kind);
            return (
              <tr key={`${step.kind} ${step.name}`}>
                <td>
                  <span className="step-cell">
                    <span className={`span-label step-label-${kind}`}>{stepKindName(kind)}</span>
                    <span className="mono truncate" title={step.name}>
                      {step.name}
                    </span>
                  </span>
                </td>
                <td className="number">{step.calls_per_request.toFixed(1)}</td>
                <td className="number mono">{formatDuration(step.avg_ms)}</td>
                <td className="number mono">{formatDuration(step.p95_ms)}</td>
                <td className="number mono">{formatDuration(step.total_ms)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {detail.steps.length === 0 && (
        <p className="empty-row text-secondary">
          No steps recorded inside this API: only the request itself was timed.
        </p>
      )}
    </section>
  );
}
