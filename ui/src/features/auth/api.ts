// Sign-in API: who is signed in, sign in, first-time setup and sign out.
import { ApiError, apiJson, apiResponse } from "../../api/client";
import {
  ACCEPT_INVITE_PATH,
  AUTH_LOGIN_PATH,
  AUTH_LOGOUT_PATH,
  AUTH_ME_PATH,
  AUTH_SETUP_PATH,
  INSPECT_INVITE_PATH,
  STATUS_UNAUTHORIZED,
} from "../../constants/api";

export type Role = "owner" | "admin" | "member" | "viewer";

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  organization: string;
}

export interface LoginForm {
  email: string;
  password: string;
}

export interface SetupForm extends LoginForm {
  token: string;
  name: string;
  organization: string;
}

/**
 * The signed-in person, or null when nobody is signed in.
 *
 * @throws ApiError for anything but 401, or TypeError when the server can't be reached.
 */
export async function fetchCurrentUser(signal: AbortSignal): Promise<CurrentUser | null> {
  try {
    return await apiJson<CurrentUser>(AUTH_ME_PATH, { signal });
  } catch (error) {
    if (error instanceof ApiError && error.status === STATUS_UNAUTHORIZED) return null;
    throw error;
  }
}

/**
 * Sign in; the server sets the session cookies.
 *
 * @throws ApiError 401 invalid_login for a wrong email or password.
 */
export function signIn(form: LoginForm): Promise<CurrentUser> {
  return apiJson<CurrentUser>(AUTH_LOGIN_PATH, { method: "POST", body: form });
}

/**
 * Create the owner with the setup token and sign them in.
 *
 * @throws ApiError 410 setup_link_invalid when the link is used or expired, 400 for a bad field.
 */
export function completeSetup(form: SetupForm): Promise<CurrentUser> {
  return apiJson<CurrentUser>(AUTH_SETUP_PATH, { method: "POST", body: form });
}

/** What an invite is for, shown before accepting it. */
export interface InviteDetails {
  email: string;
  role: Role;
  organization: string;
  invited_by: string | null;
}

/**
 * Who an invite link is for.
 *
 * @throws ApiError 410 invite_invalid when the link is wrong, used, cancelled or expired.
 */
export function inspectInvite(token: string, signal: AbortSignal): Promise<InviteDetails> {
  return apiJson<InviteDetails>(INSPECT_INVITE_PATH, { method: "POST", body: { token }, signal });
}

/**
 * Accept an invite: creates the account and signs in.
 *
 * @throws ApiError 410 invite_invalid, or 400 for a weak password.
 */
export function acceptInvite(form: { token: string; name: string; password: string }): Promise<CurrentUser> {
  return apiJson<CurrentUser>(ACCEPT_INVITE_PATH, { method: "POST", body: form });
}

/** End this session on the server and clear its cookies. */
export async function signOut(): Promise<void> {
  await apiResponse(AUTH_LOGOUT_PATH, { method: "POST" });
}
