// The Users page's data and actions. Every change reloads users and invites.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import * as zod from "zod";

import { INVITES_QUERY_KEY, USERS_QUERY_KEY } from "../../../constants/api";
import { EMAIL_PATTERN } from "../../../constants/auth";
import { DEFAULT_INVITE_ROLE, INVITE_EMAIL_MESSAGE, PICK_PROJECTS_MESSAGE } from "../../../constants/team";
import { canLimitProjects, inviteLink } from "../../../lib/team";
import type { Role } from "../../auth/api";
import {
  cancelInvite,
  changeRole,
  createInvite,
  fetchInvites,
  fetchUsers,
  removeUser,
  setProjectAccess,
  type ProjectAccess,
} from "../api";

function useReloadTeam() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: [USERS_QUERY_KEY] }),
      queryClient.invalidateQueries({ queryKey: [INVITES_QUERY_KEY] }),
    ]);
}

/** Users, pending invites, and changing a role or projects, removing a user or cancelling an invite. */
export function useTeam() {
  const reload = useReloadTeam();
  const users = useQuery({ queryKey: [USERS_QUERY_KEY], queryFn: ({ signal }) => fetchUsers(signal) });
  const invites = useQuery({ queryKey: [INVITES_QUERY_KEY], queryFn: ({ signal }) => fetchInvites(signal) });
  const role = useMutation({
    mutationFn: ({ userId, newRole }: { userId: string; newRole: Role }) => changeRole(userId, newRole),
    onSettled: reload,
  });
  const access = useMutation({
    mutationFn: ({ userId, projects }: { userId: string; projects: ProjectAccess }) =>
      setProjectAccess(userId, projects),
    onSettled: reload,
  });
  const remove = useMutation({ mutationFn: removeUser, onSettled: reload });
  const cancel = useMutation({ mutationFn: cancelInvite, onSettled: reload });
  return {
    users: users.data?.data ?? [],
    invites: invites.data?.data ?? [],
    changeRole: (userId: string, newRole: Role) => {
      role.mutate({ userId, newRole });
    },
    /** Resolves to whether it saved, so the editor closes only then; a failure shows in `error`. */
    setAccess: (userId: string, projects: ProjectAccess): Promise<boolean> =>
      access.mutateAsync({ userId, projects }).then(
        () => true,
        () => false,
      ),
    remove: (userId: string) => {
      remove.mutate(userId);
    },
    cancel: (inviteId: string) => {
      cancel.mutate(inviteId);
    },
    error: users.error ?? invites.error ?? role.error ?? access.error ?? remove.error ?? cancel.error,
  };
}

const inviteSchema = zod
  .object({
    email: zod.string().trim().toLowerCase().regex(EMAIL_PATTERN, INVITE_EMAIL_MESSAGE),
    role: zod.enum(["owner", "admin", "member", "viewer"]),
    access: zod.enum(["all", "some"]),
    projectIds: zod.array(zod.string()),
  })
  .superRefine((values, context) => {
    if (canLimitProjects(values.role) && values.access === "some" && values.projectIds.length === 0) {
      context.addIssue({ code: "custom", path: ["projectIds"], message: PICK_PROJECTS_MESSAGE });
    }
  });
type InviteValues = zod.infer<typeof inviteSchema>;

/** What the server gets: owners and admins always get all projects. */
function toAccess(values: InviteValues): ProjectAccess {
  const limited = canLimitProjects(values.role) && values.access === "some";
  return { all_projects: !limited, project_ids: limited ? values.projectIds : [] };
}

/**
 * The invite form. After inviting, `createdLink` is the link to send (shown once) until dismissed.
 *
 * @param origin - This UI's address, e.g. window.location.origin; the link opens here.
 */
export function useInviteForm(origin: string) {
  const reload = useReloadTeam();
  const form = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", role: DEFAULT_INVITE_ROLE, access: "all", projectIds: [] },
  });
  const [role, access] = useWatch({ control: form.control, name: ["role", "access"] });
  const create = useMutation({
    mutationFn: createInvite,
    onSuccess: () => {
      form.reset();
      void reload();
    },
  });
  const { errors } = form.formState;
  return {
    register: form.register,
    /** Show the project choice only for roles that can be limited. */
    showsProjects: canLimitProjects(role),
    showsProjectList: canLimitProjects(role) && access === "some",
    submit: form.handleSubmit((values) => {
      create.mutate({ email: values.email, role: values.role, ...toAccess(values) });
    }),
    inviting: create.isPending,
    created: create.data ? { email: create.data.item.email, link: inviteLink(origin, create.data.token) } : null,
    dismissCreated: () => {
      create.reset();
    },
    fieldProblem: errors.email?.message ?? errors.projectIds?.message ?? null,
    serverError: create.error,
  };
}
