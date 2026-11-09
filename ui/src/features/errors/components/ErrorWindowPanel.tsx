import { Link } from "react-router";

import { COMING_LATER } from "../../../constants/storage";
import { ERROR_WINDOW_REQUESTS, FIRST_SERVER_ERROR } from "../../../constants/errors";
import { statusMeaning } from "../../../lib/errors";
import { formatRangeTime, formatTableTime } from "../../../lib/formatTime";
import { formatDuration } from "../../../lib/waterfall";
import type { ErrorBucket, ErrorWindow } from "../api";

interface ErrorWindowPanelProps {
  bucket: ErrorBucket;
  end: string;
  window: ErrorWindow | null;
  loading: boolean;
  timeZone: string;
  requestsLink: string;
  logsLink: string;
  traceLinkOf: (traceId: string) => string;
  onOpenTrace: (traceId: string) => void;
}

/** The chosen bar: its counts, links to Requests and Logs, failures by status and API, and the newest failing requests. */
export function ErrorWindowPanel(props: ErrorWindowPanelProps) {
  const { bucket, window, timeZone } = props;
  const when = `${formatRangeTime(Date.parse(bucket.at), timeZone)} to ${formatRangeTime(Date.parse(props.end), timeZone)}`;
  return (
    <section className="panel error-window" aria-label="Chosen moment">
      <div className="page-heading">
        <h2 className="panel-title">{when}</h2>
        <p className="text-secondary">
          <strong className="error-text-server">{bucket.server_errors.toLocaleString("en")}</strong> server errors (5xx) ·{" "}
          <strong className="error-text-client">{bucket.client_errors.toLocaleString("en")}</strong> request errors (4xx) ·{" "}
          {bucket.requests.toLocaleString("en")} requests in total
        </p>
      </div>
      <div className="error-actions">
        {bucket.server_errors > 0 && (
          <Link className="button button-secondary" to={props.requestsLink}>
            Open failed requests in Requests
          </Link>
        )}
        <Link className="button button-secondary" to={props.logsLink}>
          Open error logs for {when}
        </Link>
        <button type="button" className="button button-secondary" disabled title={COMING_LATER}>
          Open grouped errors
        </button>
      </div>
      {props.loading && <p className="text-secondary">Loading the requests…</p>}
      {window && <ByStatus window={window} />}
      {window && <FailedRequests {...props} window={window} />}
    </section>
  );
}

/** The interval's failing requests counted per status code and API, most first. */
function ByStatus({ window }: { window: ErrorWindow }) {
  return (
    <div className="panel-table">
      <h3 className="error-section-title">By status code and API</h3>
      <table className="key-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Meaning</th>
            <th>API</th>
            <th className="number">Count</th>
          </tr>
        </thead>
        <tbody>
          {window.groups.map((group) => (
            <tr key={`${String(group.status)} ${group.service} ${group.http_method} ${group.route}`}>
              <td>
                <span className="status-pill" data-error="true" data-client={group.status < FIRST_SERVER_ERROR}>
                  {group.status}
                </span>
              </td>
              <td className="text-secondary">{statusMeaning(group.status)}</td>
              <td className="mono">
                {group.http_method} {group.route}
              </td>
              <td className="number">{group.requests.toLocaleString("en")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The interval's newest failing requests; a row opens its waterfall. */
function FailedRequests({ window, timeZone, traceLinkOf, onOpenTrace }: ErrorWindowPanelProps & { window: ErrorWindow }) {
  return (
    <div className="panel-table">
      <h3 className="error-section-title">Requests · newest first · select one to open its trace</h3>
      <table className="key-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Request</th>
            <th>Status</th>
            <th className="number">Took</th>
            <th>From</th>
            <th>What the code logged</th>
          </tr>
        </thead>
        <tbody>
          {window.requests.map((request) => (
            <tr
              key={request.span_id}
              className="clickable-row"
              onClick={() => {
                onOpenTrace(request.trace_id);
              }}
            >
              <td className="mono text-sm">
                <Link
                  className="request-link"
                  to={traceLinkOf(request.trace_id)}
                  onClick={(event) => {
                    event.stopPropagation();
                  }}
                >
                  {formatTableTime(request.start_ts, timeZone)}
                </Link>
              </td>
              <td className="mono">
                {request.http_method} {request.route}
              </td>
              <td>
                <span className="status-pill" data-error="true" data-client={request.http_status < FIRST_SERVER_ERROR}>
                  {request.http_status}
                </span>
              </td>
              <td className="number mono">{formatDuration(request.duration_ms)}</td>
              <td className="mono text-sm text-secondary">{request.client_ip || "-"}</td>
              <td className="error-logged mono text-sm" title={request.logged}>{request.logged || <span className="text-muted">Nothing</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {window.total > window.requests.length && (
        <p className="empty-row text-secondary">
          Showing the newest {Math.min(ERROR_WINDOW_REQUESTS, window.requests.length)} of {window.total.toLocaleString("en")}.
          Open them in Requests to see more.
        </p>
      )}
    </div>
  );
}
