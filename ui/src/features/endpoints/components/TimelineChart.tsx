import { CHART_HEIGHT, CHART_WIDTH } from "../../../constants/traces";
import { timelineChart } from "../../../lib/endpoints";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatDuration } from "../../../lib/waterfall";
import type { TimelinePoint } from "../api";

interface TimelineChartProps {
  points: TimelinePoint[];
  start: string;
  end: string;
  bucketSeconds: number;
  timeZone: string;
}

/** Requests per interval as bars (failures in red at the bottom), with the slow-5% line on top. */
export function TimelineChart({ points, start, end, bucketSeconds, timeZone }: TimelineChartProps) {
  const chart = timelineChart(points, start, end, bucketSeconds);
  const at = (iso: string) => formatRangeTime(Date.parse(iso), timeZone);
  return (
    <figure className="timeline-chart">
      <div className="timeline-chart-scale text-xs text-secondary">
        <span>
          <span className="swatch step-db" aria-hidden="true" /> Requests (up to {chart.maxRequests.toLocaleString("en")}{" "}
          per interval)
        </span>
        <span>
          <span className="swatch timeline-swatch-error" aria-hidden="true" /> Failed
        </span>
        <span>
          <span className="swatch step-llm" aria-hidden="true" /> Slow 5% (p95), up to {formatDuration(chart.maxP95Ms)}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${String(CHART_WIDTH)} ${String(CHART_HEIGHT)}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Requests and slow-5% time from ${at(start)} to ${at(end)}`}
      >
        {chart.bars.map((bar) => (
          <g key={bar.point.at}>
            <title>
              {`${at(bar.point.at)}: ${bar.point.requests.toLocaleString("en")} requests, ${bar.point.errors.toLocaleString("en")} failed, p95 ${formatDuration(bar.point.p95_ms)}`}
            </title>
            <rect
              className="timeline-bar"
              x={bar.x}
              y={CHART_HEIGHT - bar.requestsHeight}
              width={bar.width}
              height={bar.requestsHeight}
            />
            {bar.errorsHeight > 0 && (
              <rect
                className="timeline-bar-error"
                x={bar.x}
                y={CHART_HEIGHT - bar.errorsHeight}
                width={bar.width}
                height={bar.errorsHeight}
              />
            )}
          </g>
        ))}
        {chart.p95Segments.map((segment) => (
          <polyline key={segment} className="timeline-p95" points={segment} />
        ))}
      </svg>
      <figcaption className="timeline-chart-axis text-xs text-secondary mono">
        <span>{at(start)}</span>
        <span>{at(end)}</span>
      </figcaption>
    </figure>
  );
}
