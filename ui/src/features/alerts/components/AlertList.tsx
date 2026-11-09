import { useState } from "react";
import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import {
  ALERT_LIFECYCLE_HINT,
  MAX_RESOLUTION_NOTE_LENGTH,
  RESOLUTION_NOTE_PLACEHOLDER,
  UNASSIGNED_LABEL,
} from "../../../constants/alerts";
import {
  alertLogsLink,
  backToNormalText,
  conditionText,
  firedWith,
  howItEnded,
  openFor,
  splitAlerts,
  stateLabel,
} from "../../../lib/alerts";
import { formatRangeTime } from "../../../lib/formatTime";
import type { AlertEvent, Assignee } from "../api";

interface AlertListProps {
  events: AlertEvent[];
  loaded: boolean;
  timeZone: string;
  projectId: string;
  canRespond: boolean;
  assignees: Assignee[];
  onAcknowledge: (eventId: string) => void;
  onAssign: (eventId: string, userId: string) => void;
  onResolve: (eventId: string, note: string) => void;
}

/** Open alerts first, each with who has it and how to resolve it; then the closed ones as history. */
export function AlertList({ events, loaded, timeZone, ...actions }: AlertListProps) {
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
      {open.length > 0 && (
        <div className="alert-cards">
          {open.map((event) => (
            <OpenAlertCard key={event.id} event={event} at={at} {...actions} />
          ))}
        </div>
      )}
      {history.length > 0 && (
        <div className="panel panel-table">
          <table className="key-table">
            <caption>
              <span className="panel-title">History</span>
              <span className="table-caption-note text-secondary text-sm">{ALERT_LIFECYCLE_HINT}</span>
            </caption>
            <thead>
              <tr>
                <th>Alert</th>
                <th>Fired</th>
                <th>Resolved</th>
                <th>How it ended</th>
              </tr>
            </thead>
            <tbody>
              {history.map((event) => (
                <tr key={event.id}>
                  <td>
                    {event.rule_name}
                    <div className="text-muted text-xs">{conditionText(event)}</div>
                  </td>
                  <td>
                    <span className="mono">{at(event.fired_at)}</span>
                    <div className="text-muted text-xs">{firedWith(event)}</div>
                  </td>
                  <td>
                    {event.resolved_at && (
                      <>
                        <span className="mono">{at(event.resolved_at)}</span>
                        <div className="text-muted text-xs">{openFor(event.fired_at, event.resolved_at)}</div>
                      </>
                    )}
                  </td>
                  <td>
                    {howItEnded(event)}
                    {event.resolution_note && <div className="resolution-note">{event.resolution_note}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

interface OpenAlertCardProps extends Omit<AlertListProps, "events" | "loaded" | "timeZone"> {
  event: AlertEvent;
  at: (time: string) => string;
}

/** One open alert: what fired and when on the left, who has it and the actions on the right. */
function OpenAlertCard({ event, at, projectId, canRespond, assignees, onAcknowledge, onAssign, onResolve }: OpenAlertCardProps) {
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  return (
    <article className="alert-card" data-state={event.recovered_at ? "recovered" : event.state}>
      <div className="alert-card-main">
        <div className="alert-card-head">
          <span className={`status-tag alert-state-${event.state}`}>{stateLabel(event.state)}</span>
          {event.recovered_at && <span className="status-tag alert-state-recovered">Back to normal</span>}
          <h2 className="alert-card-title">{event.rule_name}</h2>
        </div>
        <span className="text-secondary text-sm">{conditionText(event)}</span>
        <span className="text-secondary text-sm">
          Fired {at(event.fired_at)} {firedWith(event)}
        </span>
        {event.recovered_at && (
          <span className="alert-card-recovered text-sm">{backToNormalText(event, at(event.recovered_at))}</span>
        )}
      </div>
      <div className="alert-card-actions">
        <label className="alert-card-owner">
          <span className="text-secondary text-sm">Assigned to</span>
          {canRespond ? (
            <select
              className="input input-compact"
              aria-label={`Assign ${event.rule_name} to`}
              value={event.assignee_id ?? ""}
              onChange={(change) => {
                if (change.target.value) onAssign(event.id, change.target.value);
              }}
            >
              <option value="" disabled>
                {UNASSIGNED_LABEL}
              </option>
              {assignees.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </select>
          ) : (
            <strong>{event.assigned_to ?? UNASSIGNED_LABEL}</strong>
          )}
        </label>
        <Link className="button button-secondary" to={alertLogsLink(projectId, event)}>
          See logs
        </Link>
        {canRespond && event.state === "firing" && (
          <Button
            onClick={() => {
              onAcknowledge(event.id);
            }}
          >
            I&apos;m on it
          </Button>
        )}
        {canRespond && !resolving && (
          <Button
            variant="primary"
            onClick={() => {
              setResolving(true);
            }}
          >
            Resolve
          </Button>
        )}
      </div>
      {canRespond && resolving && (
        <form
          className="resolve-form"
          onSubmit={(submit) => {
            submit.preventDefault();
            onResolve(event.id, note);
          }}
        >
          <label className="field">
            <span className="field-label">What did you find? (shown in the history)</span>
            <textarea
              className="input"
              rows={2}
              maxLength={MAX_RESOLUTION_NOTE_LENGTH}
              placeholder={RESOLUTION_NOTE_PLACEHOLDER}
              value={note}
              onChange={(change) => {
                setNote(change.target.value);
              }}
            />
          </label>
          <div className="dialog-actions">
            <Button
              onClick={() => {
                setResolving(false);
              }}
            >
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              Mark resolved
            </Button>
          </div>
        </form>
      )}
    </article>
  );
}
