// The "create key" form: a data key for a project, or an admin key with scopes and an expiry.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import * as zod from "zod";

import { API_KEYS_QUERY_KEY } from "../../../constants/api";
import {
  DEFAULT_ADMIN_KEY_DAYS,
  KEY_DAYS_MESSAGE,
  KEY_NAME_MESSAGE,
  KEY_PROJECT_MESSAGE,
  KEY_SCOPES_MESSAGE,
  MAX_ADMIN_KEY_DAYS,
  MAX_KEY_NAME_LENGTH,
} from "../../../constants/setup";
import { createKey, type KeyType, type NewKey } from "../api";

const keyFormSchema = zod.object({
  name: zod.string().trim().min(1, KEY_NAME_MESSAGE).max(MAX_KEY_NAME_LENGTH),
  projectId: zod.string(),
  scopes: zod.array(zod.string()),
  expiresInDays: zod.number(KEY_DAYS_MESSAGE).int().min(1, KEY_DAYS_MESSAGE).max(MAX_ADMIN_KEY_DAYS, KEY_DAYS_MESSAGE),
});
type KeyFormValues = zod.infer<typeof keyFormSchema>;

/** What the form sends for this key type; the other type's fields are left out. */
function toNewKey(keyType: KeyType, values: KeyFormValues): NewKey {
  if (keyType === "ingest") {
    return { name: values.name, key_type: keyType, project_id: values.projectId };
  }
  return {
    name: values.name,
    key_type: keyType,
    scopes: values.scopes,
    expires_in_days: values.expiresInDays,
  };
}

/**
 * Form state for creating a key of `keyType`.
 *
 * @returns `register`, `submit`, the created key (shown once) and `dismissCreated` to hide it,
 *   the first field problem and the server's error.
 */
export function useCreateKeyForm(keyType: KeyType) {
  const queryClient = useQueryClient();
  const form = useForm<KeyFormValues>({
    resolver: zodResolver(
      keyFormSchema.superRefine((values, context) => {
        if (keyType === "ingest" && values.projectId === "") {
          context.addIssue({ code: "custom", path: ["projectId"], message: KEY_PROJECT_MESSAGE });
        }
        if (keyType === "admin" && values.scopes.length === 0) {
          context.addIssue({ code: "custom", path: ["scopes"], message: KEY_SCOPES_MESSAGE });
        }
      }),
    ),
    defaultValues: { name: "", projectId: "", scopes: [], expiresInDays: DEFAULT_ADMIN_KEY_DAYS },
  });
  const create = useMutation({
    mutationFn: createKey,
    onSuccess: () => {
      form.reset();
      void queryClient.invalidateQueries({ queryKey: [API_KEYS_QUERY_KEY] });
    },
  });
  const { errors } = form.formState;
  return {
    register: form.register,
    submit: form.handleSubmit((values) => {
      create.mutate(toNewKey(keyType, values));
    }),
    creating: create.isPending,
    created: create.data ?? null,
    dismissCreated: () => {
      create.reset();
    },
    fieldProblem:
      errors.name?.message ??
      errors.projectId?.message ??
      errors.scopes?.message ??
      errors.expiresInDays?.message ??
      null,
    serverError: create.error,
  };
}
