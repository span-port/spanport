// Projects API: the list behind the project switcher and the Clients and projects page.
import { apiJson, apiResponse } from "../../api/client";
import {
  ARCHIVE_SUFFIX,
  PROJECTS_PAGE_SIZE,
  PROJECTS_PATH,
  RESTORE_SUFFIX,
} from "../../constants/api";

export interface ProjectItem {
  id: string;
  client: string;
  project: string;
  environment: string;
  /** Archived projects keep their logs, but their data keys don't work. */
  archived: boolean;
}

export interface ProjectListResponse {
  data: ProjectItem[];
  next_cursor: string | null;
  has_more: boolean;
}

/** A new project; each part is a slug such as "tracking-api". */
export interface NewProject {
  client: string;
  project: string;
  environment: string;
}

/**
 * Fetch the organization's projects (one page of up to 500).
 *
 * @throws ApiError, e.g. 401 when the session has ended.
 */
export function fetchProjects(signal: AbortSignal): Promise<ProjectListResponse> {
  return apiJson<ProjectListResponse>(`${PROJECTS_PATH}?limit=${PROJECTS_PAGE_SIZE}`, { signal });
}

/**
 * Add a project; its client is created too if new. Owners and admins only.
 *
 * @throws ApiError 409 already_exists, 403 insufficient_role or 400 for a bad name.
 */
export function createProject(project: NewProject): Promise<ProjectItem> {
  return apiJson<ProjectItem>(PROJECTS_PATH, { method: "POST", body: project });
}

/**
 * Rename a project or change its environment; its client stays the same.
 *
 * @throws ApiError 409 already_exists when the client already has that project there.
 */
export function updateProject(
  projectId: string,
  change: { project: string; environment: string },
): Promise<ProjectItem> {
  return apiJson<ProjectItem>(`${PROJECTS_PATH}/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    body: change,
  });
}

/**
 * Delete an archived project for good, with its keys and all its logs.
 *
 * @throws ApiError 409 when the project isn't archived, 503 when log storage is down.
 */
export async function deleteProject(projectId: string): Promise<void> {
  await apiResponse(`${PROJECTS_PATH}/${encodeURIComponent(projectId)}`, { method: "DELETE" });
}

/** Archive (data keys stop, logs stay) or restore a project. */
export function setProjectArchived(projectId: string, archived: boolean): Promise<ProjectItem> {
  const action = archived ? ARCHIVE_SUFFIX : RESTORE_SUFFIX;
  return apiJson<ProjectItem>(`${PROJECTS_PATH}/${encodeURIComponent(projectId)}${action}`, {
    method: "POST",
  });
}
