// The advanced text query box.
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as zod from "zod";

import { MAX_QUERY_LENGTH } from "../../../constants/logs";

const queryFormSchema = zod.object({
  query: zod.string().trim().max(MAX_QUERY_LENGTH),
});
type QueryFormValues = zod.infer<typeof queryFormSchema>;

/**
 * Form state for the text query; Enter runs it.
 *
 * @param query - The query currently applied, shown in the box.
 * @param onApply - Called with the trimmed query.
 */
export function useQueryForm(query: string, onApply: (query: string) => void) {
  const form = useForm<QueryFormValues>({
    resolver: zodResolver(queryFormSchema),
    values: { query },
  });
  return {
    register: form.register,
    submit: form.handleSubmit((values) => {
      onApply(values.query);
    }),
    error: form.formState.errors.query?.message ?? null,
  };
}
