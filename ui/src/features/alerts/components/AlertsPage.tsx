import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { ALERT_TABS } from "../../../constants/alerts";
import { useSessionStore } from "../../../state/sessionStore";
import { useCurrentUser } from "../../auth";
import { useSelectedProject } from "../../projects";
import { useAlertActions, useAlertEvents, useAlertRules, useAssignees, useRuleActions } from "../hooks/useAlerts";
import { useAlertsPage } from "../hooks/useAlertsPage";
import { AlertList } from "./AlertList";
import { RuleForm } from "./RuleForm";
import { RuleList } from "./RuleList";

/** Alerts for the selected project: what is firing now, past alerts, and the rules behind them. */
export function AlertsPage() {
  const { selected } = useSelectedProject();
  const projectId = selected?.id ?? null;
  const page = useAlertsPage(useCurrentUser().data?.role);
  const rules = useAlertRules(projectId);
  const events = useAlertEvents(projectId);
  const alertActions = useAlertActions();
  const assignees = useAssignees(projectId, page.canRespond);
  const ruleActions = useRuleActions();
  const timeZone = useSessionStore((session) => session.timeZone);
  const firing = (events.data?.data ?? []).filter((event) => event.state === "firing").length;
  const errors = [rules.error, events.error, alertActions.error, ruleActions.error];
  return (
    <div className="setup-page">
      <header className="page-heading page-heading-row">
        <div className="page-heading">
          <h1 className="page-title">Alerts</h1>
          <p className="text-secondary">What is firing now, who is handling it, and what happened before.</p>
        </div>
        {page.canManageRules && page.editing === null && selected !== null && (
          <Button variant="primary" onClick={page.startNewRule}>
            New alert rule
          </Button>
        )}
      </header>
      {selected === null && <p className="text-secondary">Add a project first: alerts belong to a project.</p>}
      <nav className="tabs" aria-label="Alerts views">
        {ALERT_TABS.map((choice) => (
          <button
            key={choice.key}
            type="button"
            className="tab"
            aria-pressed={choice.key === page.tab}
            onClick={() => {
              page.setTab(choice.key);
            }}
          >
            {choice.key === "alerts" ? `${choice.label} (${String(firing)} firing)` : choice.label}
          </button>
        ))}
      </nav>
      {errors.map((error, index) => error && <ErrorBanner key={index} error={error} />)}
      {page.tab === "alerts" ? (
        <AlertList
          events={events.data?.data ?? []}
          loaded={events.isSuccess}
          timeZone={timeZone}
          projectId={projectId ?? ""}
          canRespond={page.canRespond}
          assignees={assignees}
          onAcknowledge={alertActions.acknowledge}
          onAssign={alertActions.assign}
          onResolve={alertActions.resolve}
        />
      ) : (
        <>
          {page.canManageRules && page.editing !== null && projectId !== null && (
            <RuleForm
              key={page.editing === "new" ? "new" : page.editing.id}
              projectId={projectId}
              editing={page.editing === "new" ? null : page.editing}
              startQuery={page.startQuery}
              onDone={page.closeForm}
            />
          )}
          <RuleList
            rules={rules.data?.data ?? []}
            loaded={rules.isSuccess}
            canManage={page.canManageRules}
            actions={ruleActions}
            onEdit={page.editRule}
          />
        </>
      )}
    </div>
  );
}
