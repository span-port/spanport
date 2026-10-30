import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { INVITE_DAYS, PROJECT_ACCESS_CHOICES, ROLE_CHOICES } from "../../../constants/team";
import { useCopyText } from "../../../hooks/useCopyText";
import type { Role } from "../../auth/api";
import type { ProjectItem } from "../../projects";
import type { useInviteForm } from "../hooks/useTeam";

interface InviteFormProps {
  form: ReturnType<typeof useInviteForm>;
  roles: Role[];
  projects: ProjectItem[];
}

/**
 * Email, role and (members and viewers) which projects, then the link to send. Nobody gets access
 * until they open it and accept.
 */
export function InviteForm({ form, roles, projects }: InviteFormProps) {
  const copyLink = useCopyText();
  if (form.created) {
    return (
      <section className="panel created-key" aria-label="Invite link">
        <h2 className="panel-title">Invite link for {form.created.email}</h2>
        <p className="text-secondary text-sm">
          Send this link to {form.created.email} yourself (chat or email). It works once, for {INVITE_DAYS} days.
          They join only when they open it and press Accept; if you typed the wrong email, cancel the invite below
          and nobody gets in.
        </p>
        <div className="created-key-row">
          <code className="created-key-value">{form.created.link}</code>
          <Button
            variant="primary"
            onClick={() => {
              if (form.created) copyLink.copy(form.created.link);
            }}
          >
            {copyLink.copied ? "Copied" : "Copy link"}
          </Button>
        </div>
        {copyLink.failed && (
          <p role="alert" className="field-error">
            The browser blocked clipboard access. Select the link and copy it instead.
          </p>
        )}
        <div>
          <Button onClick={form.dismissCreated}>Done</Button>
        </div>
      </section>
    );
  }
  return (
    <form className="panel key-form" aria-label="Invite someone" noValidate onSubmit={(event) => void form.submit(event)}>
      <h2 className="panel-title">Invite someone</h2>
      <label className="field">
        <span className="field-label">Email</span>
        <input className="input" type="email" placeholder="name@yourco.com" {...form.register("email")} />
      </label>
      <fieldset className="field scope-list">
        <legend className="field-label">Role</legend>
        {ROLE_CHOICES.filter((choice) => roles.includes(choice.role)).map((choice) => (
          <label key={choice.role} className="check">
            <input type="radio" value={choice.role} {...form.register("role")} />
            {choice.label} <span className="text-muted text-xs">{choice.description}</span>
          </label>
        ))}
      </fieldset>
      {form.showsProjects ? (
        <fieldset className="field scope-list">
          <legend className="field-label">Projects they can see</legend>
          {PROJECT_ACCESS_CHOICES.map((choice) => (
            <label key={choice.value} className="check">
              <input type="radio" value={choice.value} {...form.register("access")} />
              {choice.label}
            </label>
          ))}
          {form.showsProjectList && (
            <div className="project-checks">
              {projects.map((project) => (
                <label key={project.id} className="check">
                  <input type="checkbox" value={project.id} {...form.register("projectIds")} />
                  {project.client} · {project.project} · {project.environment}
                </label>
              ))}
            </div>
          )}
        </fieldset>
      ) : (
        <p className="text-muted text-xs">Owners and admins see every project.</p>
      )}
      {form.fieldProblem && (
        <p role="alert" className="field-error">
          {form.fieldProblem}
        </p>
      )}
      {form.serverError && <ErrorBanner error={form.serverError} />}
      <div className="dialog-actions">
        <Button variant="primary" type="submit" disabled={form.inviting}>
          {form.inviting ? "Creating link..." : "Create invite link"}
        </Button>
      </div>
    </form>
  );
}
