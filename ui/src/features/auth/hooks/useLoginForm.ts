// The Sign in form: email and password.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import * as zod from "zod";

import {
  EMAIL_MESSAGE,
  EMAIL_PATTERN,
  MAX_PASSWORD_LENGTH,
  PASSWORD_REQUIRED_MESSAGE,
} from "../../../constants/auth";
import { signIn, type LoginForm } from "../api";
import { useSignedIn } from "./useSignedIn";

const loginSchema = zod.object({
  email: zod.string().trim().regex(EMAIL_PATTERN, EMAIL_MESSAGE),
  password: zod.string().min(1, PASSWORD_REQUIRED_MESSAGE).max(MAX_PASSWORD_LENGTH),
});

/**
 * Form state for signing in.
 *
 * @returns `register` for the inputs, `submit`, whether a sign-in is running, the first field
 *   problem and the server's error (wrong email or password, or the server being down).
 */
export function useLoginForm() {
  const signedIn = useSignedIn();
  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const login = useMutation({ mutationFn: signIn, onSuccess: signedIn.enter });
  const { errors } = form.formState;
  return {
    register: form.register,
    submit: form.handleSubmit((values) => {
      login.mutate(values);
    }),
    signingIn: login.isPending,
    fieldProblem: errors.email?.message ?? errors.password?.message ?? null,
    serverError: login.error,
  };
}
