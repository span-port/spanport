import { LATER_RELEASE_NOTE } from "../../../constants/ui";
import type { ProjectItem } from "../api";

interface ProjectSwitcherProps {
  projects: ProjectItem[];
  selectedId: string | null;
  onSelect: (projectId: string) => void;
}

/** Pick the project to show, as client · project · environment. "All projects" comes later. */
export function ProjectSwitcher({ projects, selectedId, onSelect }: ProjectSwitcherProps) {
  if (projects.length === 0) {
    return (
      <label className="sidebar-project">
        Project
        <select className="input" disabled value="">
          <option value="">No projects yet</option>
        </select>
      </label>
    );
  }
  return (
    <label className="sidebar-project">
      Project
      <select
        className="input"
        value={selectedId ?? ""}
        onChange={(event) => {
          onSelect(event.target.value);
        }}
      >
        <option value="" disabled title={LATER_RELEASE_NOTE}>
          All projects
        </option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.client} · {project.project} · {project.environment}
            {project.archived && " (archived)"}
          </option>
        ))}
      </select>
    </label>
  );
}
