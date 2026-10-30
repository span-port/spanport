// What each role may do in the UI. The server checks the same rules; this only hides what
// someone can't use.
import type { Role } from "../features/auth/api";

/** Owners and admins manage projects, keys, users and alert rules. */
export function isManager(role: Role | undefined): boolean {
  return role === "owner" || role === "admin";
}
