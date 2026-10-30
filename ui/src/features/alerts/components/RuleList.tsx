import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { DELETE_CONFIRM_LABEL } from "../../../constants/setup";
import { conditionText, testSentMessage } from "../../../lib/alerts";
import type { AlertRule } from "../api";
import type { useRuleActions } from "../hooks/useAlerts";

interface RuleListProps {
  rules: AlertRule[];
  loaded: boolean;
  canManage: boolean;
  actions: ReturnType<typeof useRuleActions>;
  onEdit: (rule: AlertRule) => void;
}

/** The project's rules: what each watches and who it emails; owners and admins change them. */
export function RuleList({ rules, loaded, canManage, actions, onEdit }: RuleListProps) {
  if (loaded && rules.length === 0) {
    return (
      <p className="panel empty-row text-secondary">
        No alert rules yet.{" "}
        {canManage ? "Add one above, or use Create alert on the Logs page." : "Owners and admins add them."}
      </p>
    );
  }
  const tested = rules.find((rule) => rule.id === actions.testedRuleId);
  return (
    <>
      {tested && (
        <p role="status" className="banner banner-success">
          {testSentMessage(tested)}
        </p>
      )}
      <div className="panel panel-table">
        <table className="key-table">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Emails</th>
              <th>Status</th>
              {canManage && <th aria-label="Actions" />}
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <RuleRow key={rule.id} rule={rule} canManage={canManage} actions={actions} onEdit={onEdit} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

interface RuleRowProps {
  rule: AlertRule;
  canManage: boolean;
  actions: ReturnType<typeof useRuleActions>;
  onEdit: (rule: AlertRule) => void;
}

/** One rule. Delete needs a second click, since it also removes the rule's alert history. */
function RuleRow({ rule, canManage, actions, onEdit }: RuleRowProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  return (
    <tr>
      <td>
        {rule.name}
        <div className="text-muted text-xs">{conditionText(rule)}</div>
      </td>
      <td className="text-sm">{rule.email_recipients.join(", ")}</td>
      <td>
        <span className={`status-tag status-${rule.enabled ? "active" : "revoked"}`}>
          {rule.enabled ? "on" : "off"}
        </span>
      </td>
      {canManage && (
        <td className="cell-actions">
          <Button
            className="button-small"
            disabled={actions.testing}
            onClick={() => {
              actions.test(rule.id);
            }}
          >
            Send test
          </Button>
          <Button
            className="button-small"
            onClick={() => {
              onEdit(rule);
            }}
          >
            Edit
          </Button>
          <Button
            className="button-small"
            onClick={() => {
              actions.toggle(rule);
            }}
          >
            {rule.enabled ? "Turn off" : "Turn on"}
          </Button>
          <Button
            className="button-small button-danger-text"
            onClick={() => {
              if (confirmingDelete) actions.remove(rule.id);
              else setConfirmingDelete(true);
            }}
          >
            {confirmingDelete ? DELETE_CONFIRM_LABEL : "Delete"}
          </Button>
        </td>
      )}
    </tr>
  );
}
