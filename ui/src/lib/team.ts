// Pure helpers for users and invites: role names, who may change whom, and invite links.
import { ALL_PROJECTS_LABEL, FULL_ACCESS_ROLES, PROJECT_LIST_JOINER, ROLE_CHOICES } from "../constants/team";
import { ACCEPT_INVITE_ROUTE, INVITE_TOKEN_PARAM } from "../constants/ui";
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

/** The link the invited person opens, on this UI's own address. */
export function inviteLink(origin: string, token: string): string {
  const params = new URLSearchParams({ [INVITE_TOKEN_PARAM]: token });
  return `${origin}${ACCEPT_INVITE_ROUTE}?${params.toString()}`;
}
