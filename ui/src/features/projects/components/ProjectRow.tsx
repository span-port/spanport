import { useState } from "react";
import { Link } from "react-router";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { ARCHIVE_CONFIRM_LABEL } from "../../../constants/setup";
import { API_KEYS_ROUTE } from "../../../constants/ui";
import { environmentLabel } from "../../../lib/environments";
import type { ProjectItem } from "../api";
import { useProjectActions } from "../hooks/useProjectActions";

interface ProjectRowProps {
  project: ProjectItem;
  /** Environments to choose from when renaming. */
  environments: string[];
}

/**
 * One project: rename it, archive it (two clicks), or when archived restore it or delete it for
 * good (type its name to confirm).
 */
export function ProjectRow({ project, environments }: ProjectRowProps) {
  const actions = useProjectActions(project.id);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(project.project);
  const [environment, setEnvironment] = useState(project.environment);
  const [confirmingArchive, setConfirmingArchive] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [typedName, setTypedName] = useState("");

  if (editing) {
    return (
      <form
        className="list-row list-row-editing"
        aria-label={`Rename ${project.project}`}
        onSubmit={(event) => {
          event.preventDefault();
          void actions.rename(name, environment).then(() => {
            setEditing(false);
          });
        }}
      >
        <span className="list-row-main">
          <input
            className="input input-compact"
            aria-label="Project name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
          <select
            className="input input-compact"
            aria-label="Environment"
            value={environment}
            onChange={(event) => {
              setEnvironment(event.target.value);
            }}
          >
            {environments.map((choice) => (
              <option key={choice} value={choice}>
                {environmentLabel(choice)}
              </option>
            ))}
          </select>
        </span>
        <span className="list-row-actions">
          <Button className="button-small" variant="primary" type="submit" disabled={actions.busy}>
            Save
          </Button>
          <Button
            className="button-small"
            onClick={() => {
              setEditing(false);
            }}
          >
            Cancel
          </Button>
        </span>
        {actions.error && <ErrorBanner error={actions.error} />}
      </form>
    );
  }

  return (
    <div className="list-row" data-archived={project.archived}>
      <span className="list-row-main">
        <strong>{project.project}</strong>
        <span className={`env-tag env-${project.environment}`}>{project.environment}</span>
        {project.archived && (
          <span className="text-muted text-sm">Archived: keys stopped, logs kept until they expire</span>
        )}
      </span>
      <span className="list-row-actions">
        {project.archived ? (
          <>
            <Button
              className="button-small"
              disabled={actions.busy}
              onClick={() => {
                actions.setArchived(false);
              }}
            >
              Restore
            </Button>
            {!confirmingDelete && (
              <Button
                className="button-small button-danger-text"
                onClick={() => {
                  setConfirmingDelete(true);
                }}
              >
                Delete
              </Button>
            )}
          </>
        ) : (
          <>
            <Link className="text-sm" to={API_KEYS_ROUTE}>
              Create data key
            </Link>
            <Button
              className="button-small"
              onClick={() => {
                setEditing(true);
              }}
            >
              Rename
            </Button>
            <Button
              className="button-small button-danger-text"
              disabled={actions.busy}
              onClick={() => {
                if (confirmingArchive) actions.setArchived(true);
                else setConfirmingArchive(true);
              }}
            >
              {confirmingArchive ? ARCHIVE_CONFIRM_LABEL : "Archive"}
            </Button>
          </>
        )}
      </span>
      {confirmingDelete && (
        <div className="delete-confirm" role="group" aria-label={`Delete ${project.project}`}>
          <p>
            This deletes <strong>{project.project}</strong>, its keys and{" "}
            <strong>all its logs</strong>. It can&apos;t be undone. Type{" "}
            <code className="code-inline">{project.project}</code> to confirm.
          </p>
          <span className="delete-confirm-actions">
            <input
              className="input input-compact"
              aria-label="Type the project name to confirm"
              value={typedName}
              onChange={(event) => {
                setTypedName(event.target.value);
              }}
            />
            <Button
              className="button-small button-danger"
              disabled={typedName !== project.project || actions.busy}
              onClick={actions.deleteForever}
            >
              Delete forever
            </Button>
            <Button
              className="button-small"
              onClick={() => {
                setConfirmingDelete(false);
                setTypedName("");
              }}
            >
              Cancel
            </Button>
          </span>
        </div>
      )}
      {actions.error && <ErrorBanner error={actions.error} />}
    </div>
  );
}
