// Accepting an invite: show who it is for, then create the account with a name and password.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useLocation, useNavigate } from "react-router";
import * as zod from "zod";

import { INVITE_DETAILS_QUERY_KEY } from "../../../constants/api";
import {
  MAX_NAME_LENGTH,
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  NAME_MESSAGE,
  WEAK_PASSWORD_MESSAGE,
} from "../../../constants/auth";
import { ACCEPT_INVITE_ROUTE } from "../../../constants/ui";
import { passwordStrength, strengthFill, strengthMessage } from "../../../lib/passwordStrength";
import { inviteTokenFrom } from "../../../lib/team";
import { acceptInvite, inspectInvite } from "../api";
import { useSignedIn } from "./useSignedIn";

const acceptSchema = zod.object({
  name: zod.string().trim().min(1, NAME_MESSAGE).max(MAX_NAME_LENGTH),
  password: zod.string().min(MIN_PASSWORD_LENGTH, WEAK_PASSWORD_MESSAGE).max(MAX_PASSWORD_LENGTH),
});
type AcceptValues = zod.infer<typeof acceptSchema>;

/**
 * The invite token from the link, kept in state; the address bar is then cleared of it so it
 * isn't left in history or shared by copying the address.
 *
 * @returns The token, or null when the link has none.
 */
function useInviteToken(): string | null {
  const location = useLocation();
  const navigate = useNavigate();
  const [token] = useState(() => inviteTokenFrom(location.hash, location.search));
  const linkHasToken = inviteTokenFrom(location.hash, location.search) !== null;
  useEffect(() => {
    if (linkHasToken) void navigate(ACCEPT_INVITE_ROUTE, { replace: true });
  }, [linkHasToken, navigate]);
  return token;
}

/**
 * The invite in the URL (`#token=`, or `?token=` from older links) and the form that
 * accepts it.
 *
 * @returns `token` (null when the link is incomplete), the invite's details or error, and the
 *   form: `register`, `submit`, the password meter, the first field problem, the server's error.
 */
export function useAcceptInvite() {
  const token = useInviteToken();
  const signedIn = useSignedIn();
  const details = useQuery({
    queryKey: [INVITE_DETAILS_QUERY_KEY, token],
    queryFn: ({ signal }) => inspectInvite(token ?? "", signal),
    enabled: token !== null,
  });
  const form = useForm<AcceptValues>({
    resolver: zodResolver(acceptSchema),
    defaultValues: { name: "", password: "" },
  });
  const password = useWatch({ control: form.control, name: "password" });
  const accept = useMutation({ mutationFn: acceptInvite, onSuccess: signedIn.enter });
  const { errors } = form.formState;
  const strength = passwordStrength(password);
  return {
    token,
    details,
    register: form.register,
    submit: form.handleSubmit((values) => {
      if (token !== null) accept.mutate({ token, ...values });
    }),
    accepting: accept.isPending,
    strength,
    strengthFill: strengthFill(password),
    strengthMessage: strengthMessage(strength),
    fieldProblem: errors.name?.message ?? errors.password?.message ?? null,
    serverError: accept.error,
  };
}
