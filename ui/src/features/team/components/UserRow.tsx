import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { PROJECT_ACCESS_CHOICES, REMOVE_CONFIRM_LABEL } from "../../../constants/team";
import { canLimitProjects, projectAccessLabel, roleLabel } from "../../../lib/team";
import type { Role } from "../../auth/api";
import type { ProjectItem } from "../../projects";
import type { ProjectAccess, TeamUser } from "../api";

interface UserRowProps {
  user: TeamUser;
  editable: boolean;
  roles: Role[];
  projects: ProjectItem[];
  onRole: (userId: string, role: Role) => void;
  /** Resolves to whether the change was saved. */
  onProjects: (userId: string, access: ProjectAccess) => Promise<boolean>;
  onRemove: (userId: string) => void;
}

/** One person: role, which projects they see (Edit for members and viewers), and Remove. */
export function UserRow({ user, editable, roles, projects, onRole, onProjects, onRemove }: UserRowProps) {
  const [confirming, setConfirming] = useState(false);
  const [draft, setDraft] = useState<ProjectAccess | null>(null);
  const limitable = editable && canLimitProjects(user.role);
  return (
    <tr>
      <td>{user.name}</td>
      <td>{user.email}</td>
      <td>
        {editable ? (
          <select
            className="input input-compact"
            aria-label={`Role of ${user.email}`}
            value={user.role}
            onChange={(event) => {
              const picked = roles.find((role) => role === event.target.value);
              if (picked) onRole(user.id, picked);
            }}
          >
            {roles.map((role) => (
              <option key={role} value={role}>
                {roleLabel(role)}
              </option>
            ))}
          </select>
        ) : (
          roleLabel(user.role)
        )}
      </td>
      <td>
        {draft === null ? (
          <span className="text-sm">{projectAccessLabel(user, projects)}</span>
        ) : (
          <ProjectAccessEditor
            email={user.email}
            draft={draft}
            projects={projects}
            onChange={setDraft}
            onSave={() => {
              void onProjects(user.id, draft).then((saved) => {
                if (saved) setDraft(null);
              });
            }}
            onCancel={() => {
              setDraft(null);
            }}
          />
        )}
      </td>
      <td className="cell-actions">
        {limitable && draft === null && (
          <Button
            className="button-small"
            onClick={() => {
              setDraft({ all_projects: user.all_projects, project_ids: user.project_ids });
            }}
          >
            Edit projects
          </Button>
        )}
        {editable && (
          <Button
            className="button-small button-danger-text"
            onClick={() => {
              if (confirming) onRemove(user.id);
              else setConfirming(true);
            }}
          >
            {confirming ? REMOVE_CONFIRM_LABEL : "Remove"}
          </Button>
        )}
      </td>
    </tr>
  );
}

interface ProjectAccessEditorProps {
  email: string;
  draft: ProjectAccess;
  projects: ProjectItem[];
  onChange: (access: ProjectAccess) => void;
  onSave: () => void;
  onCancel: () => void;
}

/** All projects, or tick the ones this person may see. */
function ProjectAccessEditor({ email, draft, projects, onChange, onSave, onCancel }: ProjectAccessEditorProps) {
  const toggle = (projectId: string) => {
    const project_ids = draft.project_ids.includes(projectId)
      ? draft.project_ids.filter((id) => id !== projectId)
      : [...draft.project_ids, projectId];
    onChange({ ...draft, project_ids });
  };
  return (
    <fieldset className="scope-list" aria-label={`Projects ${email} can see`}>
      {PROJECT_ACCESS_CHOICES.map((choice) => (
        <label key={choice.value} className="check">
          <input
            type="radio"
            name={`project-access-${email}`}
            checked={draft.all_projects === (choice.value === "all")}
            onChange={() => {
              onChange({ ...draft, all_projects: choice.value === "all" });
            }}
          />
          {choice.label}
        </label>
      ))}
      {!draft.all_projects &&
        projects.map((project) => (
          <label key={project.id} className="check project-check">
            <input
              type="checkbox"
              checked={draft.project_ids.includes(project.id)}
              onChange={() => {
                toggle(project.id);
              }}
            />
            {project.client} · {project.project} · {project.environment}
          </label>
        ))}
      <div className="dialog-actions">
        <Button className="button-small" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          className="button-small"
          variant="primary"
          disabled={!draft.all_projects && draft.project_ids.length === 0}
          onClick={onSave}
        >
          Save
        </Button>
      </div>
    </fieldset>
  );
}
