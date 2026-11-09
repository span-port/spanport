import { Link } from "react-router";

import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { StatCard } from "../../../components/ui/StatCard";
import { COMING_LATER } from "../../../constants/storage";
import {
  MORE_ENDPOINTS_NOTE,
  NO_REQUESTS_NOTE,
  PERCENTILE_HELP,
  SLOWER_THAN_P50,
  SLOWER_THAN_P95,
  SLOWER_THAN_P99,
  STEP_KINDS,
} from "../../../constants/traces";
import {
  dominantStep,
  errorRate,
  layerTimes,
  p95Change,
  p95RiseNote,
  percentileExample,
  slowerCount,
  stepShares,
} from "../../../lib/endpoints";
import { formatDuration, stepKindName } from "../../../lib/waterfall";
import type { EndpointStats } from "../api";
import { useEndpoints } from "../hooks/useEndpoints";
import { ApiTabs } from "./ApiTabs";
import { LatencyOverview } from "./LatencyOverview";
import { RangeControls } from "./RangeControls";
import { SlowQueries } from "./SlowQueries";

/** How fast each API of the project is, how often it fails, and where its time goes. */
export function ApisPage() {
  const endpoints = useEndpoints();
  const { summary, project, range } = endpoints;
  const showsServices = new Set(summary?.data.map((endpoint) => endpoint.service)).size > 1;
  const change = summary ? p95Change(summary.totals.p95_ms, summary.totals.previous_p95_ms) : null;
  return (
    <div className="setup-page">
      <ApiTabs />
      <header className="page-heading page-heading-row">
        <div className="page-heading">
          <h1 className="page-title">APIs</h1>
          <p className="text-secondary">
            How fast each API in{" "}
            <strong className="text-primary">
              {project ? `${project.client} · ${project.project} · ${project.environment}` : "this project"}
            </strong>{" "}
            is, and where its time goes · <strong className="text-primary">{range.name}</strong>
          </p>
        </div>
        <RangeControls range={range} />
      </header>
      {endpoints.error && <ErrorBanner error={endpoints.error} />}
      {summary && (
        <div className="stat-cards">
          <StatCard label="Requests" value={summary.totals.requests.toLocaleString("en")} />
          <StatCard label="Error rate" value={errorRate(summary.totals.errors, summary.totals.requests)} />
          <StatCard
            label="Slow 5% (p95): 95 of 100 requests were faster"
            value={
              <>
                {formatDuration(summary.totals.p95_ms)}{" "}
                {change && (
                  <span className="stat-change" data-worse={change.worse}>
                    {change.text}
                  </span>
                )}
              </>
            }
          />
          <StatCard label="LLM spend" value={<span className="text-muted text-sm">{COMING_LATER}</span>} />
        </div>
      )}
      {summary?.data[0] && <PercentileHelp example={summary.data[0]} />}
      {endpoints.slowest && endpoints.slowestTimeline && (
        <LatencyOverview
          endpoint={endpoints.slowest}
          detail={endpoints.slowestTimeline}
          start={range.start}
          end={range.end}
          timeZone={range.timeZone}
          link={endpoints.linkTo(endpoints.slowest)}
        />
      )}
      <section className="panel panel-table" aria-label="All APIs">
        <div className="table-heading">
          <h2 className="panel-title">All APIs</h2>
          <StepLegend />
        </div>
        <table className="key-table endpoint-table">
          <thead>
            <tr>
              <th>API</th>
              <th className="number">Requests</th>
              <th className="number">Errors</th>
              <th className="number" title={PERCENTILE_HELP.p50}>
                Typical <span className="th-note">p50</span>
              </th>
              <th className="number" title={PERCENTILE_HELP.p95}>
                Slow 5% <span className="th-note">p95</span>
              </th>
              <th className="number" title={PERCENTILE_HELP.p99}>
                Slowest 1% <span className="th-note">p99</span>
              </th>
              <th className="where-time-head">Where time goes</th>
              <th className="number">
                Cost <span className="th-note">per request</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {summary?.data.map((endpoint) => (
              <EndpointRow
                key={`${endpoint.service} ${endpoint.http_method} ${endpoint.route}`}
                endpoint={endpoint}
                link={endpoints.linkTo(endpoint)}
                onOpen={() => {
                  endpoints.open(endpoint);
                }}
                showService={showsServices}
              />
            ))}
          </tbody>
        </table>
        {summary?.data.length === 0 && <p className="empty-row text-secondary">{NO_REQUESTS_NOTE}</p>}
        {summary?.has_more && <p className="empty-row text-secondary">{MORE_ENDPOINTS_NOTE}</p>}
      </section>
      {summary && <SlowQueries queries={summary.slow_queries} linkTo={endpoints.linkTo} />}
    </div>
  );
}

/** What p50, p95 and p99 mean, with the busiest API's own numbers as the example. */
function PercentileHelp({ example }: { example: EndpointStats }) {
  return (
    <details className="panel percentile-help">
      <summary>What do p50, p95 and p99 mean?</summary>
      <p className="text-secondary">
        Line up an API&apos;s requests from fastest to slowest. Each one is a time that a share of them stayed under:
      </p>
      <ul className="percentile-list text-secondary">
        <li>{PERCENTILE_HELP.p50}</li>
        <li>{PERCENTILE_HELP.p95}</li>
        <li>{PERCENTILE_HELP.p99}</li>
      </ul>
      <p>{percentileExample(example)}</p>
      <p className="text-muted text-sm">Watch p95 and p99: an average hides the slow requests that users notice.</p>
    </details>
  );
}

/** A time with how many requests took longer than it, e.g. "1.9 s" over "62 slower". */
function PercentileCell({ ms, slower, strong = false }: { ms: number; slower: number; strong?: boolean }) {
  return (
    <td className={strong ? "number mono strong" : "number mono"}>
      {formatDuration(ms)}
      <div className="text-muted text-xs">{slower.toLocaleString("en")} slower</div>
    </td>
  );
}

/** The colour of each kind of step. */
function StepLegend() {
  return (
    <ul className="step-legend" aria-label="Colours">
      {STEP_KINDS.map((kind) => (
        <li key={kind}>
          <span className={`swatch step-${kind}`} aria-hidden="true" />
          {stepKindName(kind)}
        </li>
      ))}
    </ul>
  );
}

interface EndpointRowProps {
  endpoint: EndpointStats;
  link: string;
  onOpen: () => void;
  showService: boolean;
}

/** One API: its numbers, a warning when it got much slower, and where its time goes. */
function EndpointRow({ endpoint, link, onOpen, showService }: EndpointRowProps) {
  const times = layerTimes(endpoint.layers);
  const shares = stepShares(times);
  const rise = p95RiseNote(endpoint);
  return (
    <tr className="clickable-row" data-error={endpoint.errors > 0} data-warning={rise !== ""} onClick={onOpen}>
      <td>
        <Link
          className="request-link"
          to={link}
          onClick={(event) => {
            event.stopPropagation();
          }}
        >
          <span className="method-tag mono">{endpoint.http_method || "SPAN"}</span>
          <span className="mono">{endpoint.route}</span>
        </Link>
        {rise && <div className="endpoint-warning text-xs">{rise}</div>}
        {showService && <div className="text-muted text-xs">{endpoint.service}</div>}
      </td>
      <td className="number">{endpoint.requests.toLocaleString("en")}</td>
      <td className="number" data-error={endpoint.errors > 0}>
        {errorRate(endpoint.errors, endpoint.requests)}
      </td>
      <PercentileCell ms={endpoint.p50_ms} slower={slowerCount(endpoint.requests, SLOWER_THAN_P50)} />
      <PercentileCell ms={endpoint.p95_ms} slower={slowerCount(endpoint.requests, SLOWER_THAN_P95)} strong />
      <PercentileCell ms={endpoint.p99_ms} slower={slowerCount(endpoint.requests, SLOWER_THAN_P99)} />
      <td>
        <div
          className="share-bar"
          role="img"
          aria-label={shares.map((share) => `${stepKindName(share.kind)} ${String(Math.round(share.percent))}%`).join(", ")}
        >
          {shares.map((share) => (
            <span key={share.kind} className={`step-${share.kind}`} style={{ width: `${String(share.percent)}%` }} />
          ))}
        </div>
        <div className="text-muted text-xs">{dominantStep(times) || `Average ${formatDuration(endpoint.avg_ms)}`}</div>
      </td>
      <td className="number text-muted" title={COMING_LATER}>
        -
      </td>
    </tr>
  );
}
