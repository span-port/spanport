// The Alerts page's own state: which tab, which rule is being edited, and what the person may do.
import { useState } from "react";
import { useSearchParams } from "react-router";

import { ALERT_TABS, URL_PARAM_ALERT_QUERY } from "../../../constants/alerts";
import { canManageAlertRules, canRespondToAlerts } from "../../../lib/alerts";
import type { CurrentUser } from "../../auth";
import type { AlertRule } from "../api";

export type AlertsTab = (typeof ALERT_TABS)[number]["key"];

/**
 * Tab and form state. Opened from the Logs page with a search in the URL, it starts a new rule
 * with that search; closing the form drops it from the URL.
 *
 * @param role - The signed-in person's role, or undefined while loading.
 */
export function useAlertsPage(role: CurrentUser["role"] | undefined) {
  const [params, setParams] = useSearchParams();
  const startQuery = params.get(URL_PARAM_ALERT_QUERY);
  const [tab, setTab] = useState<AlertsTab>(startQuery === null ? "alerts" : "rules");
  const [editing, setEditing] = useState<AlertRule | "new" | null>(startQuery === null ? null : "new");
  return {
    tab,
    setTab,
    editing,
    startQuery: startQuery ?? "",
    canManageRules: canManageAlertRules(role),
    canRespond: canRespondToAlerts(role),
    startNewRule: () => {
      setTab("rules");
      setEditing("new");
    },
    editRule: (rule: AlertRule) => {
      setEditing(rule);
    },
    closeForm: () => {
      setEditing(null);
      if (startQuery === null) return;
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.delete(URL_PARAM_ALERT_QUERY);
        return next;
      });
    },
  };
}
