// The organization's keys, and revoking one.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { API_KEYS_QUERY_KEY } from "../../../constants/api";
import { deleteKey, fetchKeys, renameKey, revokeKey } from "../api";

/** Load every key of the organization (owners and admins only). */
export function useApiKeys() {
  return useQuery({
    queryKey: [API_KEYS_QUERY_KEY],
    queryFn: ({ signal }) => fetchKeys(signal),
  });
}

/** `rename(id, name)` renames a key and reloads the list; resolves once saved. */
export function useRenameKey() {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: ({ keyId, name }: { keyId: string; name: string }) => renameKey(keyId, name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [API_KEYS_QUERY_KEY] }),
  });
  return {
    rename: (keyId: string, name: string) => mutation.mutateAsync({ keyId, name }),
    renaming: mutation.isPending,
    error: mutation.error,
  };
}

/** `remove(id)` deletes a revoked key and reloads the list. */
export function useDeleteKey() {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: deleteKey,
    onSettled: () => queryClient.invalidateQueries({ queryKey: [API_KEYS_QUERY_KEY] }),
  });
  return {
    remove: (keyId: string) => {
      mutation.mutate(keyId);
    },
    error: mutation.error,
  };
}

/** `revoke(id)` revokes a key and reloads the list. */
export function useRevokeKey() {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: revokeKey,
    onSettled: () => queryClient.invalidateQueries({ queryKey: [API_KEYS_QUERY_KEY] }),
  });
  return {
    revoke: (keyId: string) => {
      mutation.mutate(keyId);
    },
    revoking: mutation.isPending,
    error: mutation.error,
  };
}
