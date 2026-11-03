import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { RangeChoice } from "../../../components/ui/RangeChoice";
import { NO_REQUESTS_NOTE, PERCENT, REQUEST_RANGES } from "../../../constants/traces";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatDuration } from "../../../lib/waterfall";
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
        <div className="page-heading">
          <h1 className="page-title">Requests</h1>
          <p className="text-secondary">
            Every request your apps handled. Open one to see its controller, service, database and outgoing calls on a
            timeline.
          </p>
        </div>
        <div className="heading-actions">
          <RangeChoice
            label="Time range"
            choices={REQUEST_RANGES}
            value={filters.range}
            onChange={(range) => {
              requests.change({ range });
            }}
          />
          <Button onClick={requests.refresh}>Refresh</Button>
        </div>
      </header>
      <div className="filter-bar" role="search">
        <input
          className="input filter-search"
          type="search"
          aria-label="Route contains"
          placeholder="Route contains, e.g. /users  (press Enter)"
          defaultValue={filters.route}
          key={filters.route}
          onKeyDown={(event) => {
            if (event.key === "Enter") requests.change({ route: event.currentTarget.value.trim() });
          }}
        />
        <label className="filter-field">
          Slower than
          <input
            className="input input-amount"
            type="number"
            min={0}
            aria-label="Slower than (ms)"
            placeholder="0"
            defaultValue={filters.minMs || ""}
            onKeyDown={(event) => {
              if (event.key === "Enter") requests.change({ minMs: Number(event.currentTarget.value) || 0 });
            }}
          />
          ms
        </label>
        <label className="filter-field">
          <input
            type="checkbox"
            checked={filters.errorsOnly}
            onChange={(event) => {
              requests.change({ errorsOnly: event.target.checked });
            }}
          />
          Errors only
        </label>
        {filters.service && (
          <button
            type="button"
            className="filter-chip"
            aria-label={`Show every service, not only ${filters.service}`}
            onClick={() => {
              requests.change({ service: "" });
            }}
          >
            Service: {filters.service} ✕
          </button>
        )}
      </div>
      {requests.error && <ErrorBanner error={requests.error} />}
      <div className="panel panel-table">
        <table className="key-table request-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Service</th>
              <th>Request</th>
              <th>Status</th>
              <th className="duration-head">Duration</th>
            </tr>
          </thead>
          <tbody>
            {requests.rows.map((row) => (
              <tr
                key={`${row.trace_id}${row.span_id}`}
                className="clickable-row"
                data-error={row.error}
                onClick={() => {
                  requests.open(row.trace_id);
                }}
              >
                <td className="mono text-secondary">{formatRangeTime(Date.parse(row.start_ts), timeZone)}</td>
                <td className="text-secondary">{row.service}</td>
                <td>
                  <Link
                    className="request-link"
                    to={requests.linkTo(row.trace_id)}
                    onClick={(event) => {
                      event.stopPropagation();
                    }}
                  >
                    <span className="method-tag mono">{row.http_method || "SPAN"}</span>
                    <span className="mono">{row.http_route || row.name}</span>
                  </Link>
                </td>
                <td>
                  {row.http_status > 0 && (
                    <span className="status-pill" data-error={row.error}>
                      {row.http_status}
                    </span>
                  )}
                </td>
                <td>
                  <span className="duration-cell">
                    <span className="duration-bar" aria-hidden="true">
                      <span
                        className="duration-fill"
                        data-error={row.error}
                        style={{ width: `${String((row.duration_ms / (requests.slowestMs || 1)) * PERCENT)}%` }}
                      />
                    </span>
                    <span className="mono">{formatDuration(row.duration_ms)}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!requests.loading && requests.rows.length === 0 && (
          <p className="empty-row text-secondary">{NO_REQUESTS_NOTE}</p>
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
