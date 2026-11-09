import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { StatCard } from "../../../components/ui/StatCard";
import { COMING_LATER, DATA_TABS, ESTIMATE_NOTE, REDIS_NOT_USED_NOTE } from "../../../constants/storage";
import { formatRangeTime } from "../../../lib/formatTime";
import { formatBytes, sharePercent } from "../../../lib/storage";
import { useSessionStore } from "../../../state/sessionStore";
import type { ProjectStorage, TableUsage } from "../api";
import { useStorage } from "../hooks/useStorage";

/** Setup -> Data: what Spanport stores for each project, how big it is and how long it's kept. */
export function DataPage() {
  const storage = useStorage();
  const timeZone = useSessionStore((session) => session.timeZone);
  const { summary } = storage;
  const totalBytes = summary ? summary.totals.logs.estimated_bytes + summary.totals.spans.estimated_bytes : 0;
  const since = (usage: TableUsage) => (usage.oldest ? formatRangeTime(Date.parse(usage.oldest), timeZone) : "none");
  return (
    <div className="setup-page">
      <header className="page-heading page-heading-row">
        <div className="page-heading">
          <h1 className="page-title">Data</h1>
          <p className="text-secondary">What Spanport stores for each project, how big it is, and how long it is kept.</p>
        </div>
        <Button onClick={storage.refresh}>Refresh</Button>
      </header>
      <nav className="tabs" aria-label="Data sections">
        {DATA_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className="tab"
            aria-pressed={tab.key === "storage"}
            disabled={!tab.ready}
            title={tab.ready ? undefined : COMING_LATER}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {storage.error && <ErrorBanner error={storage.error} />}
      {summary && (
        <>
          <div className="stat-cards">
            <StatCard
              label={`Logs · kept ${String(summary.logs_retention_days)} days`}
              value={formatBytes(summary.totals.logs.estimated_bytes)}
            />
            <StatCard
              label={`Traces · kept ${String(summary.spans_retention_days)} days`}
              value={formatBytes(summary.totals.spans.estimated_bytes)}
            />
            <StatCard label="Log lines" value={summary.totals.logs.rows.toLocaleString("en")} />
            <StatCard label="Request steps" value={summary.totals.spans.rows.toLocaleString("en")} />
          </div>
          <section className="panel panel-table" aria-label="Storage per project">
            <div className="table-heading">
              <h2 className="panel-title">Per project</h2>
              <span className="text-muted text-xs">{ESTIMATE_NOTE}</span>
            </div>
            <table className="key-table storage-table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th className="number">Log lines</th>
                  <th>Oldest log</th>
                  <th className="number">Request steps</th>
                  <th>Oldest step</th>
                  <th className="share-head">Size</th>
                </tr>
              </thead>
              <tbody>
                {summary.projects.map((item) => (
                  <ProjectRow key={item.project_id} item={item} totalBytes={totalBytes} since={since} />
                ))}
              </tbody>
            </table>
          </section>
          <section className="panel storage-redis" aria-label="Redis">
            <h2 className="panel-title">Redis</h2>
            <p className="text-secondary">{summary.redis_in_use ? "In use." : REDIS_NOT_USED_NOTE}</p>
          </section>
        </>
      )}
    </div>
  );
}

interface ProjectRowProps {
  item: ProjectStorage;
  totalBytes: number;
  since: (usage: TableUsage) => string;
}

/** One project: its rows, how far back they go, and its share of everything stored. */
function ProjectRow({ item, totalBytes, since }: ProjectRowProps) {
  const bytes = item.logs.estimated_bytes + item.spans.estimated_bytes;
  return (
    <tr>
      <td>
        {item.client} · {item.project}
        <div className="text-muted text-xs">{item.environment}</div>
      </td>
      <td className="number">{item.logs.rows.toLocaleString("en")}</td>
      <td className="mono text-secondary">{since(item.logs)}</td>
      <td className="number">{item.spans.rows.toLocaleString("en")}</td>
      <td className="mono text-secondary">{since(item.spans)}</td>
      <td>
        <span className="duration-cell">
          <span className="duration-bar" aria-hidden="true">
            <span className="duration-fill" style={{ width: `${String(sharePercent(bytes, totalBytes))}%` }} />
          </span>
          <span className="mono">{formatBytes(bytes)}</span>
        </span>
      </td>
    </tr>
  );
}
