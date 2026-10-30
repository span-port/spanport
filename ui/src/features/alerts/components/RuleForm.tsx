import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { ALERT_SEARCH_PRESETS, MAX_ALERT_EMAILS, MAX_ALERT_WINDOW_MINUTES } from "../../../constants/alerts";
import { previewText, thresholdExplained } from "../../../lib/alerts";
import type { AlertRule } from "../api";
import { useAlertRuleForm } from "../hooks/useAlertRuleForm";
import { useRulePreview } from "../hooks/useRulePreview";

interface RulePreviewProps {
  projectId: string;
  query: string;
  threshold: number;
  windowMinutes: number;
}

/** What the rule would say right now, or why the search can't run yet. */
function RulePreview({ projectId, query, threshold, windowMinutes }: RulePreviewProps) {
  const preview = useRulePreview(projectId, query, windowMinutes);
  if (preview.error) {
    return (
      <p role="status" className="field-error">
        {preview.error.message}
      </p>
    );
  }
  if (!preview.data) return null;
  return (
    <p role="status" className="text-secondary text-sm">
      {previewText(preview.data.total, threshold, windowMinutes)}
    </p>
  );
}

interface RuleFormProps {
  projectId: string;
  editing: AlertRule | null;
  startQuery: string;
  onDone: () => void;
}

/** "Email these people when there are more than N lines matching this search in M minutes." */
export function RuleForm({ projectId, editing, startQuery, onDone }: RuleFormProps) {
  const form = useAlertRuleForm(projectId, editing, startQuery, onDone);
  return (
    <form
      className="panel key-form"
      aria-label={editing ? "Edit alert rule" : "New alert rule"}
      noValidate
      onSubmit={(event) => void form.submit(event)}
    >
      <h2 className="panel-title">{editing ? `Edit ${editing.name}` : "New alert rule"}</h2>
      <label className="field">
        <span className="field-label">Name</span>
        <input className="input" placeholder="e.g. Too many errors" {...form.register("name")} />
      </label>
      <div className="field">
        <span className="field-label">Which log lines to count</span>
        <div className="preset-row" role="group" aria-label="Ready-made searches">
          {ALERT_SEARCH_PRESETS.map((preset) => (
            <Button
              key={preset.label}
              className="button-small"
              aria-pressed={form.watched.query === preset.query}
              onClick={() => {
                form.pickSearch(preset.query);
              }}
            >
              {preset.label}
            </Button>
          ))}
        </div>
        <input
          className="input mono"
          aria-label="Search"
          placeholder='or type a search, e.g. "payment failed" service:checkout'
          {...form.register("query")}
        />
        <span className="text-muted text-xs">
          Words in quotes match the message. The easiest way: build the search with filters on the Logs page, then
          press Create alert there.
        </span>
      </div>
      <span className="field-label">When to send the email</span>
      <div className="alert-condition">
        <span>Email when more than</span>
        <input
          className="input input-amount"
          type="number"
          min={0}
          aria-label="Lines"
          {...form.register("threshold", { valueAsNumber: true })}
        />
        <span>matching lines arrive within</span>
        <input
          className="input input-amount"
          type="number"
          min={1}
          max={MAX_ALERT_WINDOW_MINUTES}
          aria-label="Minutes"
          {...form.register("windowMinutes", { valueAsNumber: true })}
        />
        <span>minutes.</span>
      </div>
      <p className="text-muted text-xs">{thresholdExplained(form.watched.threshold, form.watched.windowMinutes)}</p>
      <RulePreview projectId={projectId} {...form.watched} />
      <label className="field">
        <span className="field-label">Email (up to {MAX_ALERT_EMAILS}, separated by commas or new lines)</span>
        <textarea className="input" rows={2} placeholder="oncall@yourco.com" {...form.register("emails")} />
      </label>
      <p className="text-muted text-xs">
        After saving, use Send test to check every address gets the email. Alerts carry counts and the search,
        never log lines.
      </p>
      {form.fieldProblem && (
        <p role="alert" className="field-error">
          {form.fieldProblem}
        </p>
      )}
      {form.serverError && <ErrorBanner error={form.serverError} />}
      <div className="dialog-actions">
        <Button onClick={onDone}>Cancel</Button>
        <Button variant="primary" type="submit" disabled={form.saving}>
          {form.saving ? "Saving..." : "Save rule"}
        </Button>
      </div>
    </form>
  );
}
