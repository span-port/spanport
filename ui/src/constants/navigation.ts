// The sidebar, grouped as in the PRD. Screens without a path are not built yet and show disabled.
import { ALERTS_ROUTE, API_KEYS_ROUTE, LOGS_ROUTE, PROJECTS_ROUTE, REQUESTS_ROUTE, USERS_ROUTE } from "./ui";

export interface NavItem {
  label: string;
  path: string | null;
  /** Shown only to owners and admins (the screen manages projects, keys or people). */
  managersOnly?: boolean;
}

export const NAV_HOME: NavItem = { label: "Home", path: null };

export const NAV_GROUPS: readonly { title: string; items: readonly NavItem[] }[] = [
  {
    title: "Monitor",
    items: [
      { label: "Requests", path: REQUESTS_ROUTE },
      { label: "APIs", path: null },
      { label: "Errors", path: null },
      { label: "Logs", path: LOGS_ROUTE },
      { label: "Web app", path: null },
      { label: "Metrics", path: null },
    ],
  },
  {
    title: "AI",
    items: [
      { label: "Quality", path: null },
      { label: "Gateway rules", path: null },
    ],
  },
  {
    title: "Spend",
    items: [
      { label: "Costs", path: null },
      { label: "Claude Code", path: null },
    ],
  },
  {
    title: "Setup",
    items: [
      { label: "Clients and projects", path: PROJECTS_ROUTE, managersOnly: true },
      { label: "API keys", path: API_KEYS_ROUTE, managersOnly: true },
      { label: "Users", path: USERS_ROUTE, managersOnly: true },
      { label: "Providers", path: null },
      { label: "Alerts", path: ALERTS_ROUTE },
      { label: "Data", path: null },
      { label: "Settings", path: null },
    ],
  },
];
