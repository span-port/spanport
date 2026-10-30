import { Button } from "../../../components/ui/Button";
import { conditionText, splitAlerts, stateLabel } from "../../../lib/alerts";
import { formatRangeTime } from "../../../lib/formatTime";
import type { AlertEvent } from "../api";

interface AlertListProps {
  events: AlertEvent[];
  loaded: boolean;
  timeZone: string;
  canRespond: boolean;
  onAcknowledge: (eventId: string) => void;
  onResolve: (eventId: string) => void;
}

/** Open alerts first, with "I'm on it" and "Mark resolved"; then the resolved ones as history. */
export function AlertList({ events, loaded, timeZone, canRespond, onAcknowledge, onResolve }: AlertListProps) {
  const { open, history } = splitAlerts(events);
  const at = (time: string) => formatRangeTime(Date.parse(time), timeZone);
  if (loaded && events.length === 0) {
    return (
      <p className="panel empty-row text-secondary">
        No alerts yet. When a rule finds more lines than it allows, the alert shows here and is emailed.
      </p>
    );
  }
  return (
    <>
      {open.map((event) => (
        <article key={event.id} className="panel alert-card" data-state={event.state}>
          <div className="alert-card-head">
            <span className={`status-tag alert-state-${event.state}`}>{stateLabel(event.state)}</span>
            <h2 className="panel-title">{event.rule_name}</h2>
          </div>
          <p className="text-secondary">
            {event.matched_count.toLocaleString("en")} lines when it fired · {conditionText(event)}
          </p>
          <p className="text-muted text-sm">
            Fired {at(event.fired_at)}
            {event.acknowledged_by && ` · ${event.acknowledged_by} is on it`}
          </p>
          {canRespond && (
            <div className="dialog-actions">
              {event.state === "firing" && (
                <Button
                  onClick={() => {
                    onAcknowledge(event.id);
                  }}
                >
                  I&apos;m on it
                </Button>
              )}
              <Button
                variant="primary"
                onClick={() => {
                  onResolve(event.id);
                }}
              >
                Mark resolved
              </Button>
            </div>
          )}
        </article>
      ))}
      {history.length > 0 && (
        <div className="panel panel-table">
          <table className="key-table">
            <caption className="panel-title">History</caption>
            <thead>
              <tr>
                <th>Alert</th>
                <th>Fired</th>
                <th>Resolved</th>
                <th>By</th>
              </tr>
            </thead>
            <tbody>
              {history.map((event) => (
                <tr key={event.id}>
                  <td>
                    {event.rule_name}
                    <div className="text-muted text-xs">{conditionText(event)}</div>
                  </td>
                  <td className="mono">{at(event.fired_at)}</td>
                  <td className="mono">{event.resolved_at && at(event.resolved_at)}</td>
                  <td>{event.resolved_by ?? "Resolved itself"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
