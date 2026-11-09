// Log alerts: a project's rules (owners and admins change them) and the alerts they fired.
import { apiJson, apiResponse } from "../../api/client";
import {
  ACKNOWLEDGE_SUFFIX,
  ALERT_ASSIGNEES_PATH,
  ALERT_EVENTS_PATH,
  ASSIGN_SUFFIX,
  ALERT_RULES_PATH,
  ALERT_SETTINGS_PATH,
  ALERTS_PAGE_SIZE,
  RESOLVE_SUFFIX,
  TEST_SUFFIX,
} from "../../constants/api";

export type AlertState = "firing" | "acknowledged" | "resolved";

/** What a rule watches and who it emails. `query` uses the Logs search syntax. */
export interface AlertRuleSettings {
  name: string;
  query: string;
  threshold: number;
  window_minutes: number;
  email_recipients: string[];
  enabled: boolean;
}

export interface AlertRule extends AlertRuleSettings {
  id: string;
  project_id: string;
  created_at: string;
}

/**
 * One alert. It stays open until a person resolves it; `recovered_at` is when its logs went back
 * within the rule. `resolved_by` is null with a `resolved_at` only for alerts that closed
 * themselves before alerts waited for a person.
 */
export interface AlertEvent {
  id: string;
  rule_id: string;
  rule_name: string;
  query: string;
  threshold: number;
  window_minutes: number;
  state: AlertState;
  matched_count: number;
  fired_at: string;
  recovered_at: string | null;
  assignee_id: string | null;
  assigned_to: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_note: string | null;
}

/** Someone a project's alerts can be assigned to. */
export interface Assignee {
  id: string;
  name: string;
  email: string;
}

/** This server's alert settings (SPANPORT_ALERT_*): how often rules are checked and their limits. */
export interface AlertLimits {
  check_seconds: number;
  max_emails: number;
  max_window_minutes: number;
  max_rules_per_project: number;
}

interface Page<Item> {
  data: Item[];
  next_cursor: string | null;
  has_more: boolean;
}

const projectQuery = (projectId: string) =>
  `?project_id=${encodeURIComponent(projectId)}&limit=${String(ALERTS_PAGE_SIZE)}`;
const rulePath = (ruleId: string) => `${ALERT_RULES_PATH}/${encodeURIComponent(ruleId)}`;
const eventPath = (eventId: string) => `${ALERT_EVENTS_PATH}/${encodeURIComponent(eventId)}`;

/** This server's alert check interval and rule limits. */
export function fetchAlertLimits(signal: AbortSignal): Promise<AlertLimits> {
  return apiJson<AlertLimits>(ALERT_SETTINGS_PATH, { signal });
}

/** A project's rules, oldest first. */
export function fetchRules(projectId: string, signal: AbortSignal): Promise<Page<AlertRule>> {
  return apiJson<Page<AlertRule>>(`${ALERT_RULES_PATH}${projectQuery(projectId)}`, { signal });
}

/** A project's alerts, newest first. */
export function fetchEvents(projectId: string, signal: AbortSignal): Promise<Page<AlertEvent>> {
  return apiJson<Page<AlertEvent>>(`${ALERT_EVENTS_PATH}${projectQuery(projectId)}`, { signal });
}

/**
 * Add a rule to a project.
 *
 * @throws ApiError 400 for a bad field or query, or when email isn't set up on the server.
 */
export function createRule(projectId: string, settings: AlertRuleSettings): Promise<AlertRule> {
  return apiJson<AlertRule>(ALERT_RULES_PATH, {
    method: "POST",
    body: { project_id: projectId, ...settings },
  });
}

/** Replace a rule's settings. */
export function updateRule(ruleId: string, settings: AlertRuleSettings): Promise<AlertRule> {
  return apiJson<AlertRule>(rulePath(ruleId), { method: "PATCH", body: settings });
}

/** Delete a rule and its alert history. */
export async function deleteRule(ruleId: string): Promise<void> {
  await apiResponse(rulePath(ruleId), { method: "DELETE" });
}

/**
 * Email a test message to the rule's recipients.
 *
 * @throws ApiError 502 delivery_failed when the mail server refused it.
 */
export async function testRule(ruleId: string): Promise<void> {
  await apiResponse(`${rulePath(ruleId)}${TEST_SUFFIX}`, { method: "POST" });
}

/** Say "I'm on it" for a firing alert. */
export async function acknowledgeEvent(eventId: string): Promise<void> {
  await apiResponse(`${eventPath(eventId)}${ACKNOWLEDGE_SUFFIX}`, { method: "POST" });
}

/** Resolve an open alert, with a note on what was found (may be empty). */
export async function resolveEvent(eventId: string, note: string): Promise<void> {
  await apiResponse(`${eventPath(eventId)}${RESOLVE_SUFFIX}`, { method: "POST", body: { note } });
}

/**
 * Give an open alert to someone; they are emailed.
 *
 * @throws ApiError 400 when that person can't take this project's alerts.
 */
export async function assignEvent(eventId: string, userId: string): Promise<void> {
  await apiResponse(`${eventPath(eventId)}${ASSIGN_SUFFIX}`, { method: "POST", body: { user_id: userId } });
}

/** Everyone the project's alerts can be assigned to, by name. */
export function fetchAssignees(projectId: string, signal: AbortSignal): Promise<Page<Assignee>> {
  const query = new URLSearchParams({ project_id: projectId });
  return apiJson<Page<Assignee>>(`${ALERT_ASSIGNEES_PATH}?${query.toString()}`, { signal });
}
