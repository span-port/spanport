import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { RangeChoice } from "../../../components/ui/RangeChoice";
import { StatCard } from "../../../components/ui/StatCard";
import { MORE_ENDPOINTS_NOTE, NO_REQUESTS_NOTE, REQUEST_RANGES, STEP_KINDS } from "../../../constants/traces";
import { dominantStep, errorRate, layerTimes, stepShares } from "../../../lib/endpoints";
import { formatDuration, stepKindName } from "../../../lib/waterfall";
import type { EndpointStats } from "../api";
import { useEndpoints } from "../hooks/useEndpoints";

/** How fast each API of the project is, how often it fails, and where its time goes. */
export function ApisPage() {
  const endpoints = useEndpoints();
  const { summary } = endpoints;
  const showsServices = new Set(summary?.data.map((endpoint) => endpoint.service)).size > 1;
  return (
    <div className="setup-page">
      <header className="page-heading page-heading-row">
        <div className="page-heading">
          <h1 className="page-title">APIs</h1>
          <p className="text-secondary">
            How fast each API is, how often it fails, and where its time goes. Open one to see its requests.
          </p>
        </div>
        <div className="heading-actions">
          <RangeChoice label="Time range" choices={REQUEST_RANGES} value={endpoints.range} onChange={endpoints.changeRange} />
          <Button onClick={endpoints.refresh}>Refresh</Button>
        </div>
      </header>
      {endpoints.error && <ErrorBanner error={endpoints.error} />}
      {summary && (
        <div className="stat-cards">
          <StatCard label="Requests" value={summary.totals.requests.toLocaleString("en")} />
          <StatCard label="Error rate" value={errorRate(summary.totals.errors, summary.totals.requests)} />
          <StatCard label="Slowest 5% take longer than (p95)" value={formatDuration(summary.totals.p95_ms)} />
        </div>
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
              <th className="number">
                Typical <span className="th-note">p50</span>
              </th>
              <th className="number">
                Slow 5% <span className="th-note">p95</span>
              </th>
              <th className="number">
                Slowest 1% <span className="th-note">p99</span>
              </th>
              <th className="where-time-head">Where time goes</th>
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
    </div>
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

/** One API: its numbers, and a bar split by where an average request spends its time. */
function EndpointRow({ endpoint, link, onOpen, showService }: EndpointRowProps) {
  const times = layerTimes(endpoint.layers);
  const shares = stepShares(times);
  return (
    <tr className="clickable-row" data-error={endpoint.errors > 0} onClick={onOpen}>
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
        {showService && <div className="text-muted text-xs">{endpoint.service}</div>}
      </td>
      <td className="number">{endpoint.requests.toLocaleString("en")}</td>
      <td className="number" data-error={endpoint.errors > 0}>
        {errorRate(endpoint.errors, endpoint.requests)}
      </td>
      <td className="number mono">{formatDuration(endpoint.p50_ms)}</td>
      <td className="number mono strong">{formatDuration(endpoint.p95_ms)}</td>
      <td className="number mono">{formatDuration(endpoint.p99_ms)}</td>
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
        <div className="text-muted text-xs">
          {dominantStep(times) || `Average ${formatDuration(endpoint.avg_ms)}`}
        </div>
      </td>
    </tr>
  );
}
