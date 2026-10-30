// API keys: list, create (shown once) and revoke. Owners and admins only.
import { apiJson, apiResponse } from "../../api/client";
import { API_KEYS_PATH, KEYS_PAGE_SIZE, REVOKE_SUFFIX } from "../../constants/api";

export type KeyType = "ingest" | "admin";

export interface ApiKeyItem {
  id: string;
  name: string | null;
  key_type: KeyType;
  prefix: string;
  last_four: string;
  project_id: string | null;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyListResponse {
  data: ApiKeyItem[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface NewKey {
  name: string;
  key_type: KeyType;
  project_id?: string;
  scopes?: string[];
  expires_in_days?: number;
}

/** A new key: `key` is the full secret, which the server shows this once. */
export interface CreatedKey {
  key: string;
  item: ApiKeyItem;
}

/**
 * The organization's keys, newest first (one page of up to 500). Never includes a key.
 *
 * @throws ApiError 403 insufficient_role for members and viewers.
 */
export function fetchKeys(signal: AbortSignal): Promise<ApiKeyListResponse> {
  return apiJson<ApiKeyListResponse>(`${API_KEYS_PATH}?limit=${KEYS_PAGE_SIZE}`, { signal });
}

/**
 * Create a data key (for a project) or an admin key (scopes and expiry).
 *
 * @throws ApiError 400 for a bad field, 404 for a project outside the organization.
 */
export function createKey(newKey: NewKey): Promise<CreatedKey> {
  return apiJson<CreatedKey>(API_KEYS_PATH, { method: "POST", body: newKey });
}

/**
 * Remove a revoked key from the list for good.
 *
 * @throws ApiError 404 when the key isn't revoked (or doesn't exist).
 */
export async function deleteKey(keyId: string): Promise<void> {
  await apiResponse(`${API_KEYS_PATH}/${encodeURIComponent(keyId)}`, { method: "DELETE" });
}

/** Give a key a new name; the key itself doesn't change. */
export function renameKey(keyId: string, name: string): Promise<ApiKeyItem> {
  return apiJson<ApiKeyItem>(`${API_KEYS_PATH}/${encodeURIComponent(keyId)}`, {
    method: "PATCH",
    body: { name },
  });
}

/**
 * Revoke a key; apps using it are refused from their next request.
 *
 * @throws ApiError 404 when the key is already revoked.
 */
export async function revokeKey(keyId: string): Promise<void> {
  await apiResponse(`${API_KEYS_PATH}/${encodeURIComponent(keyId)}${REVOKE_SUFFIX}`, {
    method: "POST",
  });
}
