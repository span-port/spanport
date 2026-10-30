// A project's rules and alerts, and the actions on them. Every change reloads both lists.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ALERT_EVENTS_QUERY_KEY, ALERT_RULES_QUERY_KEY } from "../../../constants/api";
import { ALERTS_REFRESH_MS } from "../../../constants/alerts";
import { settingsOf } from "../../../lib/alerts";
import {
  acknowledgeEvent,
  deleteRule,
  fetchEvents,
  fetchRules,
  resolveEvent,
  testRule,
  updateRule,
  type AlertRule,
} from "../api";

/** The project's rules; nothing is loaded until a project is chosen. */
export function useAlertRules(projectId: string | null) {
  return useQuery({
    queryKey: [ALERT_RULES_QUERY_KEY, projectId],
    queryFn: ({ signal }) => fetchRules(projectId ?? "", signal),
    enabled: projectId !== null,
  });
}

/** The project's alerts, newest first, refreshed while the page is open. */
export function useAlertEvents(projectId: string | null) {
  return useQuery({
    queryKey: [ALERT_EVENTS_QUERY_KEY, projectId],
    queryFn: ({ signal }) => fetchEvents(projectId ?? "", signal),
    enabled: projectId !== null,
    refetchInterval: ALERTS_REFRESH_MS,
  });
}

/** Reloads rules and alerts after any change. */
function useReloadAlerts() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: [ALERT_RULES_QUERY_KEY] }),
      queryClient.invalidateQueries({ queryKey: [ALERT_EVENTS_QUERY_KEY] }),
    ]);
}

/** "I'm on it" and "Mark resolved" on an alert. */
export function useAlertActions() {
  const reload = useReloadAlerts();
  const acknowledge = useMutation({ mutationFn: acknowledgeEvent, onSettled: reload });
  const resolve = useMutation({ mutationFn: resolveEvent, onSettled: reload });
  return {
    acknowledge: (eventId: string) => {
      acknowledge.mutate(eventId);
    },
    resolve: (eventId: string) => {
      resolve.mutate(eventId);
    },
    error: acknowledge.error ?? resolve.error,
  };
}

/** Turn a rule on or off, send a test email, or delete it. `testedRuleId` is the last test sent. */
export function useRuleActions() {
  const reload = useReloadAlerts();
  const toggle = useMutation({
    mutationFn: (rule: AlertRule) =>
      updateRule(rule.id, { ...settingsOf(rule), enabled: !rule.enabled }),
    onSettled: reload,
  });
  const test = useMutation({ mutationFn: testRule });
  const remove = useMutation({ mutationFn: deleteRule, onSettled: reload });
  return {
    toggle: (rule: AlertRule) => {
      toggle.mutate(rule);
    },
    test: (ruleId: string) => {
      test.mutate(ruleId);
    },
    testing: test.isPending,
    testedRuleId: test.isSuccess ? test.variables : null,
    remove: (ruleId: string) => {
      remove.mutate(ruleId);
    },
    error: toggle.error ?? test.error ?? remove.error,
  };
}
