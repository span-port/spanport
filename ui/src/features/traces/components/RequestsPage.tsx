import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { REQUEST_RANGES } from "../../../constants/traces";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatDuration, traceLink } from "../../../lib/waterfall";
import { useSessionStore } from "../../../state/sessionStore";
import { useRequests } from "../hooks/useRequests";

/** Incoming requests of the selected project, newest first; click one for its waterfall. */
export function RequestsPage() {
  const requests = useRequests();
  const timeZone = useSessionStore((session) => session.timeZone);
  const { filters } = requests;
  return (
    <div className="setup-page">
      <header className="page-heading page-heading-row">
        <div>
          <h1 className="page-title">Requests</h1>
          <p className="text-secondary">
            Each request your apps handled, and where its time went: open one to see the controller, service,
            database and outgoing calls as a waterfall.
          </p>
        </div>
        <Button onClick={requests.refresh}>Refresh</Button>
      </header>
      <div className="panel request-filters">
        <div className="segmented" role="group" aria-label="Time range">
          {REQUEST_RANGES.map((choice) => (
            <button
              key={choice.key}
              type="button"
              className="segment"
              aria-pressed={choice.key === filters.range}
              onClick={() => {
                requests.change({ range: choice.key });
              }}
            >
              {choice.label}
            </button>
          ))}
        </div>
        <input
          className="input"
          aria-label="Route contains"
          placeholder="Route contains, e.g. /users"
          defaultValue={filters.route}
          onKeyDown={(event) => {
            if (event.key === "Enter") requests.change({ route: event.currentTarget.value.trim() });
          }}
        />
        <label className="check">
          Slower than
          <input
            className="input input-amount"
            type="number"
            min={0}
            aria-label="Slower than (ms)"
            defaultValue={filters.minMs || ""}
            onKeyDown={(event) => {
              if (event.key === "Enter") requests.change({ minMs: Number(event.currentTarget.value) || 0 });
            }}
          />
          ms
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={filters.errorsOnly}
            onChange={(event) => {
              requests.change({ errorsOnly: event.target.checked });
            }}
          />
          Errors only
        </label>
      </div>
      {requests.error && <ErrorBanner error={requests.error} />}
      <div className="panel panel-table">
        <table className="key-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Service</th>
              <th>Request</th>
              <th>Status</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {requests.rows.map((row) => (
              <tr key={`${row.trace_id}${row.span_id}`} data-error={row.error}>
                <td className="mono">{formatRangeTime(Date.parse(row.start_ts), timeZone)}</td>
                <td>{row.service}</td>
                <td>
                  <Link className="request-link" to={traceLink(row.trace_id, requests.projectId ?? "")}>
                    <span className="mono">{row.http_method}</span> {row.http_route || row.name}
                  </Link>
                </td>
                <td className={row.error ? "status-error mono" : "mono"}>{row.http_status || ""}</td>
                <td className="mono">{formatDuration(row.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!requests.loading && requests.rows.length === 0 && (
          <p className="empty-row text-secondary">
            No requests in this range. Requests appear once your app sends traces (the SDK&apos;s tracing is coming
            next).
          </p>
        )}
        {requests.hasMore && (
          <div className="empty-row">
            <Button onClick={requests.loadMore}>Load older requests</Button>
          </div>
        )}
      </div>
    </div>
  );
}
