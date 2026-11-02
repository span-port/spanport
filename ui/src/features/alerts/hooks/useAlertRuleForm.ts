// The alert rule form: name, search, "more than N lines in M minutes" and who gets the email.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import * as zod from "zod";

import { ALERT_RULES_QUERY_KEY } from "../../../constants/api";
import {
  ALERT_EMAIL_INVALID_MESSAGE,
  ALERT_NAME_MESSAGE,
  ALERT_THRESHOLD_MESSAGE,
  DEFAULT_ALERT_THRESHOLD,
  DEFAULT_ALERT_WINDOW_MINUTES,
  EMAIL_LIST_JOINER,
  MAX_ALERT_NAME_LENGTH,
  MAX_ALERT_THRESHOLD,
} from "../../../constants/alerts";
import { EMAIL_PATTERN } from "../../../constants/auth";
import { MAX_QUERY_LENGTH } from "../../../constants/logs";
import { emailsMessage, parseEmailList, windowMessage } from "../../../lib/alerts";
import { createRule, updateRule, type AlertLimits, type AlertRule, type AlertRuleSettings } from "../api";
import { useAlertLimits } from "./useAlerts";

/** The form's checks, with the window and email limits of this server. */
function ruleFormSchema(limits: AlertLimits) {
  const windowProblem = windowMessage(limits.max_window_minutes);
  return zod
    .object({
      name: zod.string().trim().min(1, ALERT_NAME_MESSAGE).max(MAX_ALERT_NAME_LENGTH),
      query: zod.string().trim().max(MAX_QUERY_LENGTH),
      threshold: zod
        .number(ALERT_THRESHOLD_MESSAGE)
        .int(ALERT_THRESHOLD_MESSAGE)
        .min(0, ALERT_THRESHOLD_MESSAGE)
        .max(MAX_ALERT_THRESHOLD, ALERT_THRESHOLD_MESSAGE),
      windowMinutes: zod
        .number(windowProblem)
        .int(windowProblem)
        .min(1, windowProblem)
        .max(limits.max_window_minutes, windowProblem),
      emails: zod.string(),
    })
    .superRefine((values, context) => {
      const addresses = parseEmailList(values.emails);
      if (addresses.length === 0 || addresses.length > limits.max_emails) {
        context.addIssue({ code: "custom", path: ["emails"], message: emailsMessage(limits.max_emails) });
        return;
      }
      const invalid = addresses.find((address) => !EMAIL_PATTERN.test(address));
      if (invalid !== undefined) {
        context.addIssue({ code: "custom", path: ["emails"], message: `${ALERT_EMAIL_INVALID_MESSAGE} ${invalid}` });
      }
    });
}
type RuleFormValues = zod.infer<ReturnType<typeof ruleFormSchema>>;

function initialValues(editing: AlertRule | null, startQuery: string): RuleFormValues {
  if (editing === null) {
    return {
      name: "",
      query: startQuery,
      threshold: DEFAULT_ALERT_THRESHOLD,
      windowMinutes: DEFAULT_ALERT_WINDOW_MINUTES,
      emails: "",
    };
  }
  return {
    name: editing.name,
    query: editing.query,
    threshold: editing.threshold,
    windowMinutes: editing.window_minutes,
    emails: editing.email_recipients.join(EMAIL_LIST_JOINER),
  };
}

function toSettings(values: RuleFormValues, enabled: boolean): AlertRuleSettings {
  return {
    name: values.name,
    query: values.query,
    threshold: values.threshold,
    window_minutes: values.windowMinutes,
    email_recipients: parseEmailList(values.emails),
    enabled,
  };
}

/**
 * Form state for a new rule in `projectId`, or for changing `editing`.
 *
 * @param projectId - The project a new rule belongs to.
 * @param editing - The rule being changed, or null for a new one.
 * @param startQuery - The search a new rule starts with (e.g. from the Logs page).
 * @param onSaved - Called once the rule is saved.
 * @returns `register`, `submit`, `saving`, the server's `limits`, the first field problem and the server's error.
 */
export function useAlertRuleForm(
  projectId: string,
  editing: AlertRule | null,
  startQuery: string,
  onSaved: () => void,
) {
  const queryClient = useQueryClient();
  const limits = useAlertLimits();
  const resolver = useMemo(() => zodResolver(ruleFormSchema(limits)), [limits]);
  const form = useForm<RuleFormValues>({
    resolver,
    defaultValues: initialValues(editing, startQuery),
  });
  const save = useMutation({
    mutationFn: (settings: AlertRuleSettings) =>
      editing === null ? createRule(projectId, settings) : updateRule(editing.id, settings),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [ALERT_RULES_QUERY_KEY] });
      onSaved();
    },
  });
  const { errors } = form.formState;
  const [query, threshold, windowMinutes] = useWatch({
    control: form.control,
    name: ["query", "threshold", "windowMinutes"],
  });
  return {
    register: form.register,
    limits,
    /** The current values, for the live preview. */
    watched: { query, threshold, windowMinutes },
    /** Use a ready-made search (e.g. "Errors"). */
    pickSearch: (presetQuery: string) => {
      form.setValue("query", presetQuery, { shouldDirty: true });
    },
    submit: form.handleSubmit((values) => {
      save.mutate(toSettings(values, editing?.enabled ?? true));
    }),
    saving: save.isPending,
    fieldProblem:
      errors.name?.message ??
      errors.query?.message ??
      errors.threshold?.message ??
      errors.windowMinutes?.message ??
      errors.emails?.message ??
      null,
    serverError: save.error,
  };
}
