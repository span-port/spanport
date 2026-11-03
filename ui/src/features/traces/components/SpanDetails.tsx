import { formatDuration, labelName, spanFailed, stepKindOf } from "../../../lib/waterfall";
import type { SpanItem } from "../api";

/** The chosen step: what it was, when it ran, how long it took itself, and every attribute. */
export function SpanDetails({ span }: { span: SpanItem }) {
  const kind = stepKindOf(span.label);
  return (
    <aside className="panel span-details" aria-label="Step details">
      <div className="span-details-head">
        <span className={`span-label step-label-${kind}`}>{labelName(span.label)}</span>
        <h2 className="span-details-name mono">{span.name}</h2>
      </div>
      <dl className="span-details-list">
        <Detail name="Service" value={span.service} />
        <Detail name="Started" value={`+${formatDuration(span.offset_ms)} into the request`} />
        <Detail name="Duration" value={formatDuration(span.duration_ms)} />
        <Detail name="Own time" value={`${formatDuration(span.self_ms)} (not in the steps inside it)`} />
        {span.http_status > 0 && <Detail name="Status" value={String(span.http_status)} />}
        {spanFailed(span) && span.status_message && <Detail name="Error" value={span.status_message} />}
        {Object.entries(span.attributes).map(([key, value]) => (
          <Detail key={key} name={key} value={value} mono />
        ))}
      </dl>
    </aside>
  );
}

/** One fact about the step. */
function Detail({ name, value, mono = false }: { name: string; value: string; mono?: boolean }) {
  return (
    <div className="span-detail">
      <dt className={mono ? "mono" : undefined}>{name}</dt>
      <dd className={mono ? "mono" : undefined}>{value}</dd>
    </div>
  );
}
