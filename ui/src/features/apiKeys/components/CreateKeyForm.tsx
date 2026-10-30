import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { ADMIN_SCOPES, MAX_ADMIN_KEY_DAYS } from "../../../constants/setup";
import type { ProjectItem } from "../../projects";
import type { KeyType } from "../api";
import type { useCreateKeyForm } from "../hooks/useCreateKeyForm";

interface CreateKeyFormProps {
  keyType: KeyType;
  projects: ProjectItem[];
  form: ReturnType<typeof useCreateKeyForm>;
  onCancel: () => void;
}

/** Name the key, then pick its project (data key) or its scopes and expiry (admin key). */
export function CreateKeyForm({ keyType, projects, form, onCancel }: CreateKeyFormProps) {
  return (
    <form
      className="panel key-form"
      aria-label="Create key"
      noValidate
      onSubmit={(event) => void form.submit(event)}
    >
      <h2 className="panel-title">{keyType === "ingest" ? "New data key" : "New admin key"}</h2>
      <p className="text-secondary text-sm">
        {keyType === "ingest"
          ? "Lets one project's apps send logs. It can only send data, not read it."
          : "Lets scripts and CI read through the API. It covers the whole organization and expires."}
      </p>
      <label className="field">
        <span className="field-label">Name</span>
        <input className="input" placeholder="e.g. tracking-prod" {...form.register("name")} />
      </label>
      {keyType === "ingest" ? (
        <label className="field">
          <span className="field-label">Project</span>
          <select className="input" {...form.register("projectId")}>
            <option value="">Choose a project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.client} · {project.project} · {project.environment}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <>
          <fieldset className="field scope-list">
            <legend className="field-label">What the key may do</legend>
            {ADMIN_SCOPES.map((choice) => (
              <label key={choice.scope} className="check">
                <input type="checkbox" value={choice.scope} {...form.register("scopes")} />
                {choice.label} <span className="text-muted text-xs">{choice.scope}</span>
              </label>
            ))}
          </fieldset>
          <label className="field">
            <span className="field-label">Expires after (days, at most {MAX_ADMIN_KEY_DAYS})</span>
            <input
              className="input input-amount"
              type="number"
              min={1}
              max={MAX_ADMIN_KEY_DAYS}
              {...form.register("expiresInDays", { valueAsNumber: true })}
            />
          </label>
        </>
      )}
      {form.fieldProblem && (
        <p role="alert" className="field-error">
          {form.fieldProblem}
        </p>
      )}
      {form.serverError && <ErrorBanner error={form.serverError} />}
      <div className="dialog-actions">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="primary" type="submit" disabled={form.creating}>
          {form.creating ? "Creating..." : "Create key"}
        </Button>
      </div>
    </form>
  );
}
