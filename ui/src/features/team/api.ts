// The organization's people and invites. Owners and admins only.
import { apiJson, apiResponse } from "../../api/client";
import { INVITES_PATH, PROJECTS_SUFFIX, USERS_PAGE_SIZE, USERS_PATH } from "../../constants/api";
import type { Role } from "../auth/api";

/** Which projects a member or viewer sees: all, or only `project_ids`. */
export interface ProjectAccess {
  all_projects: boolean;
  project_ids: string[];
}

export interface TeamUser extends ProjectAccess {
  id: string;
  name: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface PendingInvite extends ProjectAccess {
  id: string;
  email: string;
  role: Role;
  invited_by: string | null;
  created_at: string;
  expires_at: string;
}

/** A new invite: `token` goes into the link and is returned only this once. */
export interface CreatedInvite {
  token: string;
  item: PendingInvite;
}

interface Page<Item> {
  data: Item[];
  next_cursor: string | null;
  has_more: boolean;
}

const pageQuery = `?limit=${String(USERS_PAGE_SIZE)}`;

/** The organization's active users. */
export function fetchUsers(signal: AbortSignal): Promise<Page<TeamUser>> {
  return apiJson<Page<TeamUser>>(`${USERS_PATH}${pageQuery}`, { signal });
}

/** Invites waiting to be accepted. */
export function fetchInvites(signal: AbortSignal): Promise<Page<PendingInvite>> {
  return apiJson<Page<PendingInvite>>(`${INVITES_PATH}${pageQuery}`, { signal });
}

/**
 * Give a user a new role.
 *
 * @throws ApiError 403 (only owners touch owners, not yourself), 409 when no owner would be left.
 */
export function changeRole(userId: string, role: Role): Promise<TeamUser> {
  return apiJson<TeamUser>(`${USERS_PATH}/${encodeURIComponent(userId)}`, { method: "PATCH", body: { role } });
}

/**
 * Give a member or viewer all projects, or only some.
 *
 * @throws ApiError 400 for an owner or admin (they see everything) or when no project is picked.
 */
export function setProjectAccess(userId: string, access: ProjectAccess): Promise<TeamUser> {
  return apiJson<TeamUser>(`${USERS_PATH}/${encodeURIComponent(userId)}${PROJECTS_SUFFIX}`, {
    method: "PUT",
    body: access,
  });
}

/** Remove a user; they are signed out everywhere. */
export async function removeUser(userId: string): Promise<void> {
  await apiResponse(`${USERS_PATH}/${encodeURIComponent(userId)}`, { method: "DELETE" });
}

/**
 * Invite someone. Nothing is granted until they accept.
 *
 * @throws ApiError 409 when the email already has an account.
 */
export function createInvite(invite: { email: string; role: Role } & ProjectAccess): Promise<CreatedInvite> {
  return apiJson<CreatedInvite>(INVITES_PATH, { method: "POST", body: invite });
}

/** Cancel a pending invite; its link stops working. */
export async function cancelInvite(inviteId: string): Promise<void> {
  await apiResponse(`${INVITES_PATH}/${encodeURIComponent(inviteId)}`, { method: "DELETE" });
}
