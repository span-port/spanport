import { Button } from "../../../components/ui/Button";
import {
  EQUALS_OPERATOR,
  NOT_EQUALS_OPERATOR,
  TRACE_PREVIEW_LENGTH,
} from "../../../constants/logs";
import { EMPTY_VALUE, LATER_RELEASE_NOTE } from "../../../constants/ui";
import { useCopyText } from "../../../hooks/useCopyText";
import { toPrettyJson } from "../../../lib/copyFormats";
import { formatTableTime } from "../../../lib/formatTime";
import { levelTone } from "../../../lib/levels";
import { parseRequestLine, statusTone } from "../../../lib/requestLine";
import type { FilterChip, LogItem } from "../types";
import { LevelTag } from "./LevelTag";

interface LogRowProps {
  log: LogItem;
  timeZone: string;
  expanded: boolean;
  onToggle: () => void;
  /** Adds a filter chip built from a field of this line. */
  onFilter: (chip: FilterChip) => void;
}

/**
 * One log line. Expanded, it shows the whole message in a box (with its own copy button), every
 * field with Filter / Exclude to drill in, and Copy as JSON for the whole record.
 */
export function LogRow({ log, timeZone, expanded, onToggle, onFilter }: LogRowProps) {
  const copyMessage = useCopyText();
  const copyJson = useCopyText();
  const tone = levelTone(log.level);
  return (
    <div className="log-entry" data-expanded={expanded}>
      <button type="button" className="log-grid log-row" aria-expanded={expanded} onClick={onToggle}>
        <span className="text-secondary">{formatTableTime(log.ts, timeZone)}</span>
        <span>
          <LevelTag level={log.level} />
        </span>
        <span className="cell-clip text-secondary">{log.service}</span>
        <MessageCell message={log.message} tone={tone} />
        <span className="trace-cell">
          {log.trace_id ? `${log.trace_id.slice(0, TRACE_PREVIEW_LENGTH)}…` : "n/a"}
        </span>
      </button>
      {expanded && (
        <div className="log-details">
          <div className="log-details-top">
            <span className="mono text-secondary text-xs">
              {formatTableTime(log.ts, timeZone)} {timeZone} · {log.ts}
            </span>
            <Button
              className="button-small"
              onClick={() => {
                copyJson.copy(toPrettyJson(log));
              }}
            >
              {copyJson.copied ? "Copied JSON" : "Copy as JSON"}
            </Button>
          </div>
          <div className={`message-box message-box-${tone}`}>
            <pre className="message-box-text">{log.message}</pre>
            <Button
              className="button-small message-box-copy"
              aria-label="Copy message"
              onClick={() => {
                copyMessage.copy(log.message);
              }}
            >
              {copyMessage.copied ? "Copied" : "Copy"}
            </Button>
          </div>
          {(copyMessage.failed || copyJson.failed) && (
            <p role="alert" className="field-error">
              The browser blocked clipboard access. Select the text and copy it instead.
            </p>
          )}
          <dl className="detail-list detail-list-filterable">
            <DetailField name="level" field="level" value={log.level} onFilter={onFilter} />
            <DetailField name="service" field="service" value={log.service} onFilter={onFilter} />
            <DetailField name="trace_id" field="trace" value={log.trace_id} onFilter={onFilter} />
            <DetailField name="span_id" field="span" value={log.span_id} onFilter={onFilter} />
            {Object.entries(log.attributes).map(([name, value]) => (
              <DetailField key={name} name={name} field={name} value={value} onFilter={onFilter} />
            ))}
          </dl>
          <span className="link-disabled" aria-disabled="true" title={LATER_RELEASE_NOTE}>
            Open the request and its trace → ({LATER_RELEASE_NOTE.toLowerCase()})
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * The message column. A request line ("GET /api/... 500 402ms") shows as method, path with ids
 * as :id (full path on hover), status and duration, so the useful end is never cut off.
 */
function MessageCell({ message, tone }: { message: string; tone: string }) {
  const request = parseRequestLine(message);
  if (request === null) return <span className={`cell-clip message-${tone}`}>{message}</span>;
  return (
    <span className="request-line">
      <span className="request-method">{request.method}</span>
      <span className="cell-clip" title={request.path}>
        {request.template}
      </span>
      <span className={`request-status status-${statusTone(request.status)}`}>{request.status}</span>
      <span className="request-duration">{request.durationMs} ms</span>
    </span>
  );
}

interface DetailFieldProps {
  name: string;
  /** The filter field for this value, e.g. "trace" for trace_id. */
  field: string;
  value: string;
  onFilter: (chip: FilterChip) => void;
}

/** One field with Filter (show only this value) and Exclude (hide it); empty values can't. */
function DetailField({ name, field, value, onFilter }: DetailFieldProps) {
  return (
    <div className="detail-pair">
      <dt>{name}</dt>
      <dd className="detail-value">
        <span>{value || EMPTY_VALUE}</span>
        {value && (
          <span className="detail-actions">
            <button
              type="button"
              className="link-button detail-action"
              aria-label={`Show only ${name} = ${value}`}
              onClick={() => {
                onFilter({ field, operator: EQUALS_OPERATOR, value });
              }}
            >
              Filter
            </button>
            <button
              type="button"
              className="link-button detail-action"
              aria-label={`Exclude ${name} = ${value}`}
              onClick={() => {
                onFilter({ field, operator: NOT_EQUALS_OPERATOR, value });
              }}
            >
              Exclude
            </button>
          </span>
        )}
      </dd>
    </div>
  );
}
