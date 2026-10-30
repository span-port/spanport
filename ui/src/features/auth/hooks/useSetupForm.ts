// The first-time setup form: creates the owner with the one-time token from the server's log.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import * as zod from "zod";

import {
  EMAIL_MESSAGE,
  EMAIL_PATTERN,
  MAX_NAME_LENGTH,
  MAX_ORG_NAME_LENGTH,
  MAX_PASSWORD_LENGTH,
  MAX_SETUP_TOKEN_LENGTH,
  MIN_PASSWORD_LENGTH,
  NAME_MESSAGE,
  ORG_MESSAGE,
  SETUP_TOKEN_MESSAGE,
  WEAK_PASSWORD_MESSAGE,
} from "../../../constants/auth";
import { passwordStrength, strengthFill, strengthMessage } from "../../../lib/passwordStrength";
import { completeSetup, type SetupForm } from "../api";
import { useSignedIn } from "./useSignedIn";

const setupSchema = zod.object({
  token: zod.string().trim().min(1, SETUP_TOKEN_MESSAGE).max(MAX_SETUP_TOKEN_LENGTH),
  name: zod.string().trim().min(1, NAME_MESSAGE).max(MAX_NAME_LENGTH),
  email: zod.string().trim().regex(EMAIL_PATTERN, EMAIL_MESSAGE),
  password: zod.string().min(MIN_PASSWORD_LENGTH, WEAK_PASSWORD_MESSAGE).max(MAX_PASSWORD_LENGTH),
  organization: zod.string().trim().min(1, ORG_MESSAGE).max(MAX_ORG_NAME_LENGTH),
});

/**
 * Form state for creating the owner.
 *
 * @returns `register`, `submit`, the password meter, the first field problem and the server's
 *   error (used or expired token, weak password).
 */
export function useSetupForm() {
  const signedIn = useSignedIn();
  const form = useForm<SetupForm>({
    resolver: zodResolver(setupSchema),
    defaultValues: { token: "", name: "", email: "", password: "", organization: "" },
  });
  const password = useWatch({ control: form.control, name: "password" });
  const setup = useMutation({ mutationFn: completeSetup, onSuccess: signedIn.enter });
  const { errors } = form.formState;
  const strength = passwordStrength(password);
  return {
    register: form.register,
    submit: form.handleSubmit((values) => {
      setup.mutate(values);
    }),
    creating: setup.isPending,
    strength,
    strengthFill: strengthFill(password),
    strengthMessage: strengthMessage(strength),
    fieldProblem:
      errors.token?.message ??
      errors.name?.message ??
      errors.email?.message ??
      errors.password?.message ??
      errors.organization?.message ??
      null,
    serverError: setup.error,
  };
}
