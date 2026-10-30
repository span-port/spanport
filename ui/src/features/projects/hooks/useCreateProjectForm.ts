// The "add project" form: names are typed freely and stored as slugs; extra environments
// (qa, uat, ...) can be added next to the standard three.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import * as zod from "zod";

import { PROJECTS_QUERY_KEY } from "../../../constants/api";
import {
  CLIENT_MESSAGE,
  ENVIRONMENT_MESSAGE,
  PROJECT_MESSAGE,
} from "../../../constants/setup";
import { environmentChoices, similarEnvironment } from "../../../lib/environments";
import { toSlug } from "../../../lib/slug";
import { createProject, type NewProject } from "../api";

const projectFormSchema = zod.object({
  client: zod.string().refine((name) => toSlug(name) !== "", CLIENT_MESSAGE),
  project: zod.string().refine((name) => toSlug(name) !== "", PROJECT_MESSAGE),
  environment: zod.string().refine((name) => toSlug(name) !== "", ENVIRONMENT_MESSAGE),
});
type ProjectFormValues = zod.infer<typeof projectFormSchema>;

/**
 * Form state for adding a project.
 *
 * @param usedEnvironments - Environments the organization's projects already use.
 * @returns `register`, `submit`, the slugs the names will be saved as, the environments to pick
 *   from, the "add environment" draft with its near-duplicate warning, the created project, the
 *   first field problem and the server's error (e.g. already exists).
 */
export function useCreateProjectForm(usedEnvironments: string[]) {
  const queryClient = useQueryClient();
  const [addedEnvironments, setAddedEnvironments] = useState<string[]>([]);
  const [environmentDraft, setEnvironmentDraft] = useState<string | null>(null);
  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: { client: "", project: "", environment: "production" },
  });
  const [client, project, environment] = useWatch({
    control: form.control,
    name: ["client", "project", "environment"],
  });
  const create = useMutation({
    mutationFn: (values: NewProject) => createProject(values),
    onSuccess: () => {
      form.resetField("project");
      void queryClient.invalidateQueries({ queryKey: [PROJECTS_QUERY_KEY] });
    },
  });
  const choices = environmentChoices(usedEnvironments, addedEnvironments);
  const draftSlug = toSlug(environmentDraft ?? "");
  const { errors } = form.formState;
  return {
    register: form.register,
    submit: form.handleSubmit((values) => {
      create.mutate({
        client: toSlug(values.client),
        project: toSlug(values.project),
        environment: toSlug(values.environment),
      });
    }),
    clientSlug: toSlug(client),
    projectSlug: toSlug(project),
    environment,
    environments: choices,
    /** The "+ Environment" box: null while closed. */
    environmentDraft,
    draftSlug,
    draftLooksLike: similarEnvironment(draftSlug, choices),
    openEnvironmentDraft: () => {
      setEnvironmentDraft("");
    },
    setEnvironmentDraft,
    closeEnvironmentDraft: () => {
      setEnvironmentDraft(null);
    },
    /** Add the drafted environment to the choices and select it. */
    addEnvironment: () => {
      if (draftSlug === "") return;
      setAddedEnvironments((added) => [...added, draftSlug]);
      form.setValue("environment", draftSlug);
      setEnvironmentDraft(null);
    },
    creating: create.isPending,
    created: create.data ?? null,
    fieldProblem:
      errors.client?.message ?? errors.project?.message ?? errors.environment?.message ?? null,
    serverError: create.error,
  };
}
