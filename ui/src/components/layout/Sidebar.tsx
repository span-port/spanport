import { Fragment } from "react";
import { NavLink, useSearchParams } from "react-router";

import { URL_PARAM_PROJECT } from "../../constants/logs";
import { NAV_GROUPS, NAV_HOME, type NavItem } from "../../constants/navigation";
import { LATER_RELEASE_NOTE } from "../../constants/ui";
import { isManager } from "../../lib/roles";
import { useSignOut, type CurrentUser } from "../../features/auth";
import { ProjectSwitcher, useSelectedProject } from "../../features/projects";
import { BrandMark } from "../ui/BrandMark";
import { Button } from "../ui/Button";

/**
 * Logo, project switcher, the grouped navigation and who is signed in. Screens that manage
 * projects, keys or people are listed only for owners and admins.
 */
export function Sidebar({ user }: { user: CurrentUser }) {
  const { projectList, selected, select } = useSelectedProject();
  const { signOut, signingOut } = useSignOut();
  return (
    <nav aria-label="Main" className="sidebar">
      <BrandMark />
      <ProjectSwitcher projects={projectList} selectedId={selected?.id ?? null} onSelect={select} />
      <NavEntry item={NAV_HOME} />
      {NAV_GROUPS.map((group) => (
        <Fragment key={group.title}>
          <span className="nav-group">{group.title}</span>
          {group.items
            .filter((item) => !item.managersOnly || isManager(user.role))
            .map((item) => (
              <NavEntry key={item.label} item={item} />
            ))}
        </Fragment>
      ))}
      <div className="sidebar-user">
        <span className="sidebar-user-name">{user.name}</span>
        <span className="sidebar-user-line text-muted text-xs" title={user.email}>
          {user.email}
        </span>
        <span className="sidebar-user-line text-muted text-xs">
          {user.role} · {user.organization}
        </span>
        <Button onClick={signOut} disabled={signingOut}>
          Sign out
        </Button>
      </div>
    </nav>
  );
}

/**
 * A link to a built screen, or a disabled entry for one that comes later. Links keep the selected
 * project, so moving from Logs to Alerts stays on the same project.
 */
function NavEntry({ item }: { item: NavItem }) {
  const [params] = useSearchParams();
  const projectId = params.get(URL_PARAM_PROJECT);
  if (item.path === null) {
    return (
      <span className="nav-link nav-link-disabled" aria-disabled="true" title={LATER_RELEASE_NOTE}>
        {item.label}
      </span>
    );
  }
  return (
    <NavLink
      to={{
        pathname: item.path,
        search: projectId === null ? "" : new URLSearchParams({ [URL_PARAM_PROJECT]: projectId }).toString(),
      }}
      className="nav-link"
    >
      {item.label}
    </NavLink>
  );
}
