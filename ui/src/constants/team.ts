// Users and invites: the roles people can have, and the Users page's messages.
import type { Role } from "../features/auth/api";

// What each role may do, shown where a role is picked.
export const ROLE_CHOICES: readonly { role: Role; label: string; description: string }[] = [
  { role: "owner", label: "Owner", description: "Everything, including making other owners" },
  { role: "admin", label: "Admin", description: "Projects, keys, alert rules and people (not owners)" },
  { role: "member", label: "Member", description: "Sees everything and handles alerts" },
  { role: "viewer", label: "Viewer", description: "Only looks" },
];
export const DEFAULT_INVITE_ROLE: Role = "member";
// Owners and admins always see every project; only members and viewers can be limited.
export const FULL_ACCESS_ROLES: readonly Role[] = ["owner", "admin"];
export const ALL_PROJECTS_LABEL = "All projects";
export const PICK_PROJECTS_MESSAGE = "Pick at least one project, or choose All projects.";
export const PROJECT_ACCESS_CHOICES = [
  { value: "all", label: "All projects" },
  { value: "some", label: "Only these projects" },
] as const;
export const PROJECT_LIST_JOINER = ", ";
export const INVITE_DAYS = 7;
export const REMOVE_CONFIRM_LABEL = "Click again to remove";
export const CANCEL_INVITE_CONFIRM_LABEL = "Click again to cancel";
export const INVITE_EMAIL_MESSAGE = "Enter the email address of the person to invite.";
export const MISSING_INVITE_TOKEN_MESSAGE = "This page needs the full invite link. Open the link you were sent.";
