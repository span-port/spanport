import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { API_KEYS_ROUTE } from "../../../constants/ui";
import { environmentLabel } from "../../../lib/environments";
import { useCreateProjectForm } from "../hooks/useCreateProjectForm";
import { useProjects } from "../hooks/useProjects";
import { GettingStarted, HowItIsOrganized } from "./ProjectsGuide";
import { ProjectRow } from "./ProjectRow";

/** Clients and projects: what they are, add one, and rename, archive or restore them. */
export function ProjectsPage() {
  const projects = useProjects();
  const projectList = projects.data?.data ?? [];
  const form = useCreateProjectForm([...new Set(projectList.map((item) => item.environment))]);
  const byClient = Map.groupBy(projectList, (project) => project.client);
  return (
    <div className="setup-page">
      <header className="page-heading">
        <h1 className="page-title">Clients and projects</h1>
        <p className="text-secondary">
          Every log belongs to one project. Projects are grouped by the client they are for.
        </p>
      </header>
      <HowItIsOrganized />

      {form.created && (
        <div role="status" className="banner banner-success">
          Added {form.created.client} / {form.created.project} / {form.created.environment}.{" "}
          <Link to={API_KEYS_ROUTE}>Create a data key for it</Link> so its app can send logs.
        </div>
      )}

      <form className="panel" noValidate onSubmit={(event) => void form.submit(event)}>
        <h2 className="panel-title">Add a project</h2>
        <div className="form-row">
          <label className="field form-grow">
            <span className="field-label">Client</span>
            <input
              className="input"
              list="known-clients"
              placeholder="e.g. GenHRX"
              {...form.register("client")}
            />
            <datalist id="known-clients">
              {[...byClient.keys()].map((client) => (
                <option key={client} value={client} />
              ))}
            </datalist>
          </label>
          <label className="field form-grow">
            <span className="field-label">Project</span>
            <input className="input" placeholder="e.g. Backend API" {...form.register("project")} />
          </label>
        </div>
        <fieldset className="field env-picker">
          <legend className="field-label">Environment</legend>
          <div className="env-options">
            <div className="segmented">
              {form.environments.map((choice) => (
                <label key={choice} className="segment segment-radio">
                  <input type="radio" value={choice} {...form.register("environment")} />
                  {environmentLabel(choice)}
                </label>
              ))}
            </div>
            {form.environmentDraft === null && (
              <Button className="button-small" onClick={form.openEnvironmentDraft}>
                + Environment
              </Button>
            )}
          </div>
        </fieldset>
        {form.environmentDraft !== null && (
          <div className="env-draft">
            <label className="field form-grow">
              <span className="field-label">New environment</span>
              <input
                className="input"
                placeholder="e.g. QA, UAT, Preprod"
                value={form.environmentDraft}
                onChange={(event) => {
                  form.setEnvironmentDraft(event.target.value);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    form.addEnvironment();
                  }
                }}
              />
            </label>
            <Button variant="primary" disabled={form.draftSlug === ""} onClick={form.addEnvironment}>
              Add {form.draftSlug || "environment"}
            </Button>
            <Button onClick={form.closeEnvironmentDraft}>Cancel</Button>
            {form.draftLooksLike && (
              <p className="env-warning" role="status">
                You already have <strong>{form.draftLooksLike}</strong>. Use it if this is the same
                place, so its logs don&apos;t split across two names.
              </p>
            )}
          </div>
        )}
        <div className="form-footer">
          <p className="project-preview">
            <span className="text-secondary text-sm">You are adding</span>
            <span className="project-path">
              <span>{form.clientSlug || "client"}</span>
              <span className="project-path-separator">/</span>
              <span>{form.projectSlug || "project"}</span>
              <span className="project-path-separator">/</span>
              <span className={`env-tag env-${form.environment}`}>{form.environment}</span>
            </span>
          </p>
          <Button variant="primary" type="submit" disabled={form.creating}>
            {form.creating ? "Adding..." : "Add project"}
          </Button>
        </div>
        {form.fieldProblem && (
          <p role="alert" className="field-error">
            {form.fieldProblem}
          </p>
        )}
        {form.serverError && <ErrorBanner error={form.serverError} />}
      </form>

      {projects.error && <ErrorBanner error={projects.error} />}
      {projects.isSuccess && byClient.size === 0 && <GettingStarted />}

      <div className="client-grid">
        {[...byClient].map(([client, clientProjects]) => (
          <section key={client} className="panel panel-list" aria-label={`Client ${client}`}>
            <h2 className="panel-title client-title">
              <span className="client-initial" aria-hidden="true">
                {client.charAt(0).toUpperCase()}
              </span>
              {client}
              <span className="text-secondary text-sm">
                {clientProjects.length} {clientProjects.length === 1 ? "project" : "projects"}
              </span>
            </h2>
            {clientProjects.map((project) => (
              <ProjectRow key={project.id} project={project} environments={form.environments} />
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
