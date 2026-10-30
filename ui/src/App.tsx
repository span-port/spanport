import { Navigate, Route, Routes } from "react-router";

import { ManagersOnly } from "./components/layout/ManagersOnly";
import { Sidebar } from "./components/layout/Sidebar";
import { ErrorBanner } from "./components/ui/ErrorBanner";
import {
  ACCEPT_INVITE_ROUTE,
  ALERTS_ROUTE,
  ANY_ROUTE,
  API_KEYS_ROUTE,
  LOGIN_ROUTE,
  LOGS_ROUTE,
  PROJECTS_ROUTE,
  REQUESTS_ROUTE,
  SETUP_ROUTE,
  TRACE_ROUTE,
  USERS_ROUTE,
} from "./constants/ui";
import { AlertsPage } from "./features/alerts";
import { ApiKeysPage } from "./features/apiKeys";
import { AcceptInvitePage, LoginPage, SetupPage, useCurrentUser } from "./features/auth";
import { LogsPage } from "./features/logs";
import { ProjectsPage } from "./features/projects";
import { TeamPage } from "./features/team";
import { RequestsPage, TracePage } from "./features/traces";
import { useScrollToTopOnNavigate } from "./hooks/useScrollToTopOnNavigate";

/** Sign in, Set up and Accept invite are open to everyone; every other screen needs a signed-in person. */
export function App() {
  return (
    <Routes>
      <Route path={LOGIN_ROUTE} element={<LoginPage />} />
      <Route path={SETUP_ROUTE} element={<SetupPage />} />
      <Route path={ACCEPT_INVITE_ROUTE} element={<AcceptInvitePage />} />
      <Route path={ANY_ROUTE} element={<SignedInApp />} />
    </Routes>
  );
}

/** The sidebar and screens, or a redirect to Sign in when nobody is signed in. */
function SignedInApp() {
  const currentUser = useCurrentUser();
  useScrollToTopOnNavigate();
  if (currentUser.isPending) return null;
  if (currentUser.isError) {
    return (
      <main className="auth-page">
        <ErrorBanner error={currentUser.error} />
      </main>
    );
  }
  if (currentUser.data === null) return <Navigate to={LOGIN_ROUTE} replace />;
  const { role } = currentUser.data;
  return (
    <div className="app">
      <Sidebar user={currentUser.data} />
      <main className="app-main">
        <Routes>
          <Route path={LOGS_ROUTE} element={<LogsPage />} />
          <Route
            path={PROJECTS_ROUTE}
            element={
              <ManagersOnly role={role} title="Clients and projects">
                <ProjectsPage />
              </ManagersOnly>
            }
          />
          <Route
            path={API_KEYS_ROUTE}
            element={
              <ManagersOnly role={role} title="API keys">
                <ApiKeysPage />
              </ManagersOnly>
            }
          />
          <Route path={ALERTS_ROUTE} element={<AlertsPage />} />
          <Route path={REQUESTS_ROUTE} element={<RequestsPage />} />
          <Route path={TRACE_ROUTE} element={<TracePage />} />
          <Route
            path={USERS_ROUTE}
            element={
              <ManagersOnly role={role} title="Users">
                <TeamPage />
              </ManagersOnly>
            }
          />
          <Route path={ANY_ROUTE} element={<Navigate to={LOGS_ROUTE} replace />} />
        </Routes>
      </main>
    </div>
  );
}
