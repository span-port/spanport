import type { ErrorShow } from "../../../constants/errors";
import { errorChart } from "../../../lib/errors";
import { formatRangeTime } from "../../../lib/formatTime";
import type { ErrorBucket } from "../api";

interface ErrorChartProps {
  buckets: ErrorBucket[];
  bucketSeconds: number;
  start: string;
  end: string;
  show: ErrorShow;
  timeZone: string;
  chosenAt: string | null;
  onSelect: (bucket: ErrorBucket) => void;
}

/** 5xx and 4xx per interval as stacked bars; each bar is a button that shows its requests. */
export function ErrorChart({ buckets, bucketSeconds, start, end, show, timeZone, chosenAt, onSelect }: ErrorChartProps) {
  const chart = errorChart(buckets, start, end, bucketSeconds, show);
  const at = (iso: string) => formatRangeTime(Date.parse(iso), timeZone);
  return (
    <section className="panel" aria-label="Errors over time">
      <div className="table-heading">
        <h2 className="panel-title">
          Errors over time <span className="text-muted text-sm">· times in {timeZone} · select a bar</span>
        </h2>
        <ul className="step-legend" aria-label="Colours">
          {show !== "4xx" && (
            <li>
              <span className="swatch error-swatch-server" aria-hidden="true" />
              5xx
            </li>
          )}
          {show !== "5xx" && (
            <li>
              <span className="swatch error-swatch-client" aria-hidden="true" />
              4xx
            </li>
          )}
        </ul>
      </div>
      <div className="error-chart">
        <div className="error-chart-scale text-xs text-muted mono" aria-hidden="true">
          <span>{chart.maxErrors.toLocaleString("en")}</span>
          <span>{Math.round(chart.maxErrors / 2).toLocaleString("en")}</span>
          <span>0</span>
        </div>
        <div className="error-chart-plot">
          {chart.bars.map((bar) => (
            <button
              key={bar.bucket.at}
              type="button"
              className="error-bar"
              style={{ left: `${String(bar.leftPercent)}%`, width: `${String(bar.widthPercent)}%` }}
              aria-pressed={bar.bucket.at === chosenAt}
              aria-label={`${at(bar.bucket.at)}: ${bar.bucket.server_errors.toLocaleString("en")} 5xx, ${bar.bucket.client_errors.toLocaleString("en")} 4xx of ${bar.bucket.requests.toLocaleString("en")} requests`}
              title={`${at(bar.bucket.at)}: ${bar.bucket.server_errors.toLocaleString("en")} 5xx, ${bar.bucket.client_errors.toLocaleString("en")} 4xx`}
              onClick={() => {
                onSelect(bar.bucket);
              }}
            >
              <span className="error-bar-client" style={{ height: `${String(bar.clientPercent)}%` }} />
              <span className="error-bar-server" style={{ height: `${String(bar.serverPercent)}%` }} />
            </button>
          ))}
        </div>
      </div>
      <div className="timeline-chart-axis error-chart-axis text-xs text-secondary mono">
        <span>{at(start)}</span>
        <span>{at(end)}</span>
      </div>
    </section>
  );
}
