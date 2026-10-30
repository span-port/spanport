import { Navigate } from "react-router";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { RESET_PASSWORD_COMMAND } from "../../../constants/auth";
import { LATER_RELEASE_NOTE, LOGS_ROUTE } from "../../../constants/ui";
import { useCurrentUser } from "../hooks/useCurrentUser";
import { useLoginForm } from "../hooks/useLoginForm";
import { AuthCard } from "./AuthCard";

/** Sign in with email and password. Google sign-in comes later. */
export function LoginPage() {
  const currentUser = useCurrentUser();
  const form = useLoginForm();
  if (currentUser.data) return <Navigate to={LOGS_ROUTE} replace />;
  return (
    <AuthCard>
      <h1 className="auth-title">Sign in</h1>
      <Button disabled title={LATER_RELEASE_NOTE}>
        Continue with Google
      </Button>
      <div className="auth-divider">or</div>
      <form className="auth-form" noValidate onSubmit={(event) => void form.submit(event)}>
        <label className="auth-field">
          Email
          <input className="input" type="email" autoComplete="username" {...form.register("email")} />
        </label>
        <label className="auth-field">
          Password
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            {...form.register("password")}
          />
        </label>
        {form.fieldProblem && (
          <p role="alert" className="field-error">
            {form.fieldProblem}
          </p>
        )}
        {form.serverError && <ErrorBanner error={form.serverError} />}
        <Button variant="primary" type="submit" disabled={form.signingIn}>
          {form.signingIn ? "Signing in..." : "Sign in"}
        </Button>
      </form>
      <p className="auth-note">
        Forgot your password? Ask an admin to reset it. If you are the only admin, someone with
        server access can run <code className="code-inline">{RESET_PASSWORD_COMMAND}</code>.
      </p>
    </AuthCard>
  );
}
