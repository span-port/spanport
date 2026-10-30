import { useState } from "react";
import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import { canManageAlertRules, newAlertLink } from "../../../lib/alerts";
import { useCurrentUser } from "../../auth";
import type { LogExplorer, StreamState } from "../hooks/useLogExplorer";
import { CustomRangeDialog } from "./CustomRangeDialog";
import { TimeRangePicker } from "./TimeRangePicker";

/**
 * Title, live badge, the time range, pause / resume, and (owners and admins) Create alert from
 * this search. The project is in the sidebar.
 */
export function LogsHeader({ explorer }: { explorer: LogExplorer }) {
  const [customOpen, setCustomOpen] = useState(false);
  const { state, timeZone } = explorer;
  const role = useCurrentUser().data?.role;
  return (
    <header className="logs-header">
      <div className="logs-header-row">
        <div className="logs-title">
          <h1 className="page-title">Logs</h1>
          <span className={`stream-badge stream-${badgeTone(explorer.streamState)}`}>
            <span className="stream-dot" aria-hidden="true" />
            {badgeLabel(explorer.streamState)}
          </span>
        </div>
        <div className="logs-header-controls">
          <TimeRangePicker
            range={state.range}
            timeZone={timeZone}
            customOpen={customOpen}
            onSelectRange={(range) => {
              setCustomOpen(false);
              explorer.selectRange(range);
            }}
            onSelectTimeZone={explorer.setTimeZone}
            onToggleCustom={() => {
              setCustomOpen(!customOpen);
            }}
          />
          <Button onClick={explorer.togglePause}>{pauseLabel(explorer.streamState)}</Button>
          {canManageAlertRules(role) && explorer.project && (
            <Link
              className="button button-secondary"
              to={newAlertLink(explorer.project.id, explorer.searchAsQuery)}
              title="Email people when this search finds too many lines"
            >
              Create alert
            </Link>
          )}
          {/* Floats under the controls, over the page, instead of pushing everything down. */}
          {customOpen && (
            <CustomRangeDialog
              range={state.range}
              timeZone={timeZone}
              onApply={(range) => {
                setCustomOpen(false);
                explorer.selectRange(range);
              }}
              onCancel={() => {
                setCustomOpen(false);
              }}
            />
          )}
        </div>
      </div>
    </header>
  );
}

function badgeLabel(state: StreamState): string {
  switch (state) {
    case "live":
      return "Live tail";
    case "connecting":
      return "Connecting";
    case "reconnecting":
      return "Reconnecting";
    case "paused":
      return "Paused";
    case "stopped":
      return "Stopped";
    case "historical":
      return "Historical";
  }
}

function badgeTone(state: StreamState): "live" | "waiting" | "stopped" | "quiet" {
  switch (state) {
    case "live":
      return "live";
    case "connecting":
    case "reconnecting":
      return "waiting";
    case "stopped":
      return "stopped";
    case "paused":
    case "historical":
      return "quiet";
  }
}

function pauseLabel(state: StreamState): string {
  if (state === "historical") return "Back to live";
  return state === "paused" ? "Resume" : "Pause";
}
