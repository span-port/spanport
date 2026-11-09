// Pure helpers for users and invites: role names, who may change whom, and invite links.
import { ALL_PROJECTS_LABEL, FULL_ACCESS_ROLES, PROJECT_LIST_JOINER, ROLE_CHOICES } from "../constants/team";
import { ACCEPT_INVITE_ROUTE, INVITE_TOKEN_PARAM, URL_FRAGMENT_MARK } from "../constants/ui";
import type { Role } from "../features/auth/api";

/** "Owner", "Admin", "Member" or "Viewer". */
export function roleLabel(role: Role): string {
  return ROLE_CHOICES.find((choice) => choice.role === role)?.label ?? role;
}

/** The roles this person may give: only owners make owners. */
export function rolesYouCanGive(yourRole: Role | undefined): Role[] {
  return ROLE_CHOICES.map((choice) => choice.role).filter((role) => role !== "owner" || yourRole === "owner");
}

/**
 * Whether you may change or remove this user: not yourself, and only owners touch owners.
 * The server checks the same rules (and keeps at least one owner).
 */
export function canChangeUser(you: { id: string; role: Role } | undefined, user: { id: string; role: Role }): boolean {
  if (you === undefined || you.id === user.id) return false;
  return user.role !== "owner" || you.role === "owner";
}

/** Whether this role can be limited to some projects (owners and admins always see all). */
export function canLimitProjects(role: Role): boolean {
  return !FULL_ACCESS_ROLES.includes(role);
}

/** "All projects", or the projects' names, e.g. "northwind · hr-portal · production". */
export function projectAccessLabel(
  access: { all_projects: boolean; project_ids: string[] },
  projects: { id: string; client: string; project: string; environment: string }[],
): string {
  if (access.all_projects) return ALL_PROJECTS_LABEL;
  return projects
    .filter((project) => access.project_ids.includes(project.id))
    .map((project) => `${project.client} · ${project.project} · ${project.environment}`)
    .join(PROJECT_LIST_JOINER);
}

/**
 * The link the invited person opens, on this UI's own address. The token goes in the
 * fragment (`#token=...`), which browsers never send to a server, so no access log keeps it.
 */
export function inviteLink(origin: string, token: string): string {
  const params = new URLSearchParams({ [INVITE_TOKEN_PARAM]: token });
  return `${origin}${ACCEPT_INVITE_ROUTE}${URL_FRAGMENT_MARK}${params.toString()}`;
}

/**
 * The invite token in a link: from the fragment (`#token=...`), else from the query
 * (`?token=...`, links sent before the token moved to the fragment).
 *
 * @param hash - `location.hash`, with or without its leading "#".
 * @param search - `location.search`.
 * @returns The token, or null when the link has none.
 */
export function inviteTokenFrom(hash: string, search: string): string | null {
  const fromFragment = new URLSearchParams(hash.replace(URL_FRAGMENT_MARK, "")).get(INVITE_TOKEN_PARAM);
  return fromFragment ?? new URLSearchParams(search).get(INVITE_TOKEN_PARAM);
}
