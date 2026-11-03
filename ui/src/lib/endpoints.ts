// Pure helpers for the APIs screen: error rates, where the time goes, and links to the requests.
import { URL_PARAM_PROJECT } from "../constants/logs";
import {
  DEFAULT_REQUEST_RANGE,
  DOMINANT_STEP_PERCENT,
  ONE_DECIMAL_BELOW_PERCENT,
  PERCENT,
  STEP_KINDS,
  URL_PARAM_REQUEST_RANGE,
  URL_PARAM_ROUTE,
  URL_PARAM_SERVICE,
} from "../constants/traces";
import { REQUESTS_ROUTE } from "../constants/ui";
import type { EndpointLayers } from "../features/endpoints/api";
import type { StepKind, StepTimes } from "./waterfall";
import { stepKindName } from "./waterfall";

/** An endpoint's step times keyed like a trace's, so both screens share the colours and names. */
export function layerTimes(layers: EndpointLayers): StepTimes {
  return { code: layers.code_ms, db: layers.db_ms, external: layers.external_ms, llm: layers.llm_ms };
}

/** e.g. "0%", "0.4%", "1.9%" (one decimal below 10%), "25%". */
export function errorRate(errors: number, requests: number): string {
  if (requests === 0 || errors === 0) return "0%";
  const percent = (errors / requests) * PERCENT;
  return `${percent < ONE_DECIMAL_BELOW_PERCENT ? percent.toFixed(1) : String(Math.round(percent))}%`;
}

/** Each kind of step's share of the time, in display order, as percentages adding up to 100. */
export function stepShares(times: StepTimes): { kind: StepKind; percent: number }[] {
  const totalMs = STEP_KINDS.reduce((sum, kind) => sum + times[kind], 0);
  if (totalMs <= 0) return [];
  return STEP_KINDS.map((kind) => ({ kind, percent: (times[kind] / totalMs) * PERCENT })).filter(
    (share) => share.percent > 0,
  );
}

/** "Database 82%" when one kind of step takes a large share of the time, else an empty string. */
export function dominantStep(times: StepTimes): string {
  const largest = stepShares(times).reduce<{ kind: StepKind; percent: number } | null>(
    (best, share) => (best === null || share.percent > best.percent ? share : best),
    null,
  );
  if (largest === null || largest.percent < DOMINANT_STEP_PERCENT) return "";
  return `${stepKindName(largest.kind)} ${String(Math.round(largest.percent))}%`;
}

/** The Requests screen showing this endpoint's requests in the same range. */
export function endpointRequestsLink(projectId: string, range: string, service: string, route: string): string {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId });
  if (range !== DEFAULT_REQUEST_RANGE) params.set(URL_PARAM_REQUEST_RANGE, range);
  params.set(URL_PARAM_SERVICE, service);
  params.set(URL_PARAM_ROUTE, route);
  return `${REQUESTS_ROUTE}?${params.toString()}`;
}
