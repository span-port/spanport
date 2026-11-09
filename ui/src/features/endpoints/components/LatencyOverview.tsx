import { Link } from "react-router";

import { worstPoint } from "../../../lib/endpoints";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatDuration } from "../../../lib/waterfall";
import type { EndpointDetail, EndpointStats } from "../api";
import { TimelineChart } from "./TimelineChart";

interface LatencyOverviewProps {
  endpoint: EndpointStats;
  detail: EndpointDetail;
  start: string;
  end: string;
  timeZone: string;
  link: string;
}

/** The slowest API's slow-5% time over the range, and when it was at its worst. */
export function LatencyOverview({ endpoint, detail, start, end, timeZone, link }: LatencyOverviewProps) {
  const worst = worstPoint(detail.timeline);
  return (
    <section className="panel" aria-label="Latency over time">
      <div className="table-heading latency-heading">
        <h2 className="panel-title">
          Slowest 5% (p95) ·{" "}
          <Link className="mono" to={link}>
            {endpoint.http_method} {endpoint.route}
          </Link>
        </h2>
        {worst && (
          <span className="endpoint-warning text-sm">
            Worst at {formatRangeTime(Date.parse(worst.at), timeZone)}: {formatDuration(worst.p95_ms)} (p95)
          </span>
        )}
      </div>
      <TimelineChart
        points={detail.timeline}
        start={start}
        end={end}
        bucketSeconds={detail.bucket_seconds}
        timeZone={timeZone}
      />
    </section>
  );
}
