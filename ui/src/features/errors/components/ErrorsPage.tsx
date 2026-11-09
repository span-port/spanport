import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { StatCard } from "../../../components/ui/StatCard";
import {
  ERROR_SHOW_CHOICES,
  ERROR_TABS,
  ERRORS_DESCRIPTION,
  NO_ERRORS_NOTE,
  NORMAL_SERVER_ERROR_NOTE,
  NORMAL_SERVER_ERROR_SHARE,
  SECONDS_PER_MINUTE,
  SELECT_A_BAR_NOTE,
  type ErrorShow,
} from "../../../constants/errors";
import { COMING_LATER } from "../../../constants/storage";
import { requestShare } from "../../../lib/errors";
import { formatRangeTime } from "../../../lib/formatTime";
import { RangeControls } from "../../endpoints";
import type { ErrorSummary } from "../api";
import { useErrors, type ApiChoice } from "../hooks/useErrors";
import { ErrorChart } from "./ErrorChart";
import { ErrorWindowPanel } from "./ErrorWindowPanel";

/** HTTP errors over time: 4xx and 5xx per interval, and the requests behind a chosen bar. */
export function ErrorsPage() {
  const errors = useErrors();
  const { summary, range, project } = errors;
  return (
    <div className="setup-page">
      <nav className="tabs" aria-label="Errors sections">
        {ERROR_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className="tab"
            aria-pressed={tab.ready}
            disabled={!tab.ready}
            title={tab.ready ? undefined : COMING_LATER}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <header className="page-heading page-heading-row">
        <div className="page-heading">
          <h1 className="page-title">HTTP errors</h1>
          <p className="text-secondary">{ERRORS_DESCRIPTION}</p>
          <p className="text-secondary">
            <strong className="text-primary">
              {project ? `${project.client} · ${project.project} · ${project.environment}` : "This project"}
            </strong>{" "}
            · <strong className="text-primary">{range.name}</strong>
          </p>
        </div>
        <RangeControls range={range} />
      </header>
      <div className="filter-bar" role="search">
        <label className="filter-field">
          Show
          <select
            className="input input-small"
            value={errors.show}
            onChange={(event) => {
              errors.selectShow(event.target.value as ErrorShow);
            }}
          >
            {ERROR_SHOW_CHOICES.map((choice) => (
              <option key={choice.key} value={choice.key}>
                {choice.label}
              </option>
            ))}
          </select>
        </label>
        <ApiSelect apis={apiChoices(summary, errors.api)} chosen={errors.api} onSelect={errors.selectApi} />
      </div>
      {errors.error && <ErrorBanner error={errors.error} />}
      {summary && <ErrorCards summary={summary} timeZone={range.timeZone} />}
      {summary && summary.buckets.length > 0 && (
        <ErrorChart
          buckets={summary.buckets}
          bucketSeconds={summary.bucket_seconds}
          start={range.start}
          end={range.end}
          show={errors.show}
          timeZone={range.timeZone}
          chosenAt={errors.chosen?.at ?? null}
          onSelect={errors.selectBar}
        />
      )}
      {summary && summary.totals.client_errors + summary.totals.server_errors === 0 && (
        <p className="panel text-secondary">{NO_ERRORS_NOTE}</p>
      )}
      {errors.chosen && errors.chosenEnd && errors.requestsLink && errors.logsLink ? (
        <ErrorWindowPanel
          bucket={errors.chosen}
          end={errors.chosenEnd}
          window={errors.window}
          loading={errors.windowLoading}
          timeZone={range.timeZone}
          requestsLink={errors.requestsLink}
          logsLink={errors.logsLink}
          traceLinkOf={errors.traceLinkOf}
          onOpenTrace={errors.openTrace}
        />
      ) : (
        summary && summary.buckets.length > 0 && <p className="text-secondary">{SELECT_A_BAR_NOTE}</p>
      )}
    </div>
  );
}

/** The failing APIs, plus the chosen one when it had no errors in this range. */
function apiChoices(summary: ErrorSummary | null, chosen: ApiChoice): ApiChoice[] {
  const apis: ApiChoice[] = summary?.apis ?? [];
  const listed = apis.some((api) => sameApi(api, chosen));
  return chosen.route && !listed ? [chosen, ...apis] : apis;
}

function sameApi(left: ApiChoice, right: ApiChoice): boolean {
  return left.service === right.service && left.http_method === right.http_method && left.route === right.route;
}

interface ApiSelectProps {
  apis: ApiChoice[];
  chosen: ApiChoice;
  onSelect: (api: ApiChoice | null) => void;
}

/** "All APIs" or one API that failed in the range. */
function ApiSelect({ apis, chosen, onSelect }: ApiSelectProps) {
  const chosenIndex = apis.findIndex((api) => sameApi(api, chosen));
  return (
    <label className="filter-field">
      API
      <select
        className="input input-small"
        value={chosenIndex < 0 ? "" : String(chosenIndex)}
        onChange={(event) => {
          onSelect(apis[Number(event.target.value)] ?? null);
        }}
      >
        <option value="">All APIs</option>
        {apis.map((api, index) => (
          <option key={`${api.service} ${api.http_method} ${api.route}`} value={String(index)}>
            {api.http_method} {api.route}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Totals: 5xx, 4xx, the worst moment for 5xx and every request in the range. */
function ErrorCards({ summary, timeZone }: { summary: ErrorSummary; timeZone: string }) {
  const { totals } = summary;
  const serverShare = totals.requests ? totals.server_errors / totals.requests : 0;
  const worst = totals.worst_server;
  return (
    <div className="stat-cards">
      <StatCard
        label="Server errors (5xx)"
        value={totals.server_errors.toLocaleString("en")}
        tone={serverShare > NORMAL_SERVER_ERROR_SHARE ? "error" : "good"}
        note={`${requestShare(totals.server_errors, totals.requests)} of requests; ${NORMAL_SERVER_ERROR_NOTE}`}
      />
      <StatCard
        label="Request errors (4xx)"
        value={totals.client_errors.toLocaleString("en")}
        tone="warning"
        note={`${requestShare(totals.client_errors, totals.requests)} of requests`}
      />
      <StatCard
        label="Worst moment for 5xx"
        value={worst ? formatRangeTime(Date.parse(worst.at), timeZone) : "None"}
        note={
          worst
            ? `${worst.server_errors.toLocaleString("en")} server errors in ${String(summary.bucket_seconds / SECONDS_PER_MINUTE)} min`
            : "No server errors in this range"
        }
      />
      <StatCard label="Requests in range" value={totals.requests.toLocaleString("en")} note="All status codes" />
    </div>
  );
}
