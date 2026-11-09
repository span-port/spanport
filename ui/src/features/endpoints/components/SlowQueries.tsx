import { Link } from "react-router";

import { looksLikeNPlusOne } from "../../../lib/endpoints";
import { formatDuration } from "../../../lib/waterfall";
import type { EndpointStats, SlowQuery } from "../api";

interface SlowQueriesProps {
  queries: SlowQuery[];
  linkTo: (endpoint: Pick<EndpointStats, "service" | "http_method" | "route">) => string;
}

/** The database queries with the most total time, each with the API that runs it. */
export function SlowQueries({ queries, linkTo }: SlowQueriesProps) {
  return (
    <section className="panel" aria-label="Slow queries">
      <h2 className="panel-title">Slow queries</h2>
      {queries.length === 0 && (
        <p className="text-secondary">
          No database queries recorded in this range. They appear once your app&apos;s database calls are timed.
        </p>
      )}
      <div className="slow-queries">
        {queries.map((query) => (
          <div key={`${query.service} ${query.route} ${query.statement}`} className="slow-query">
            <code className="slow-query-text">{query.statement}</code>
            <div className="slow-query-facts text-sm">
              <span>
                <span className="text-secondary">Average</span> {formatDuration(query.avg_ms)}
              </span>
              <span>
                <span className="text-secondary">Slow 5%</span> {formatDuration(query.p95_ms)}
              </span>
              <span>
                <span className="text-secondary">Calls / request</span> {query.calls_per_request.toFixed(1)}
              </span>
              <span>
                <span className="text-secondary">Used by</span>{" "}
                <Link className="mono" to={linkTo(query)}>
                  {query.http_method} {query.route}
                </Link>
              </span>
              {looksLikeNPlusOne(query.calls_per_request) && (
                <span className="endpoint-warning" title="The same query runs many times in one request, often inside a loop">
                  N+1 pattern
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
