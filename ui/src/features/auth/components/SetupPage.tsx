import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { SETUP_TOKEN_COMMAND } from "../../../constants/auth";
import { LATER_RELEASE_NOTE } from "../../../constants/ui";
import { useSetupForm } from "../hooks/useSetupForm";
import { AuthCard } from "./AuthCard";

/** First-time setup: create the owner account with the one-time token from the server's log. */
export function SetupPage() {
  const form = useSetupForm();
  return (
    <AuthCard>
      <div className="auth-heading">
        <h1 className="auth-title">Set up Spanport</h1>
        <p className="text-secondary">
          Create the owner account. The setup token works once and expires in 1 hour. Find it in
          the server&apos;s log: <code className="code-inline">{SETUP_TOKEN_COMMAND}</code>
        </p>
      </div>
      <form className="auth-form" noValidate onSubmit={(event) => void form.submit(event)}>
        <label className="auth-field">
          Setup token
          <input className="input mono" type="text" autoComplete="off" {...form.register("token")} />
        </label>
        <label className="auth-field">
          Your name
          <input className="input" type="text" autoComplete="name" {...form.register("name")} />
        </label>
        <label className="auth-field">
          Email
          <input className="input" type="email" autoComplete="username" {...form.register("email")} />
        </label>
        <label className="auth-field">
          Password
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            {...form.register("password")}
          />
        </label>
        <div className="strength">
          <meter
            className={`strength-meter strength-${form.strength}`}
            min={0}
            max={1}
            value={form.strengthFill}
            aria-label="Password strength"
          />
          <span className={`strength-text strength-${form.strength}`}>{form.strengthMessage}</span>
        </div>
        <label className="auth-field">
          Organization name
          <input
            className="input"
            type="text"
            autoComplete="organization"
            {...form.register("organization")}
          />
        </label>
        <label className="auth-check" title={LATER_RELEASE_NOTE}>
          <input type="checkbox" disabled />
          <span>
            <strong>Load sample data</strong>
            <br />
            <span className="text-secondary text-sm">{LATER_RELEASE_NOTE}.</span>
          </span>
        </label>
        {form.fieldProblem && (
          <p role="alert" className="field-error">
            {form.fieldProblem}
          </p>
        )}
        {form.serverError && <ErrorBanner error={form.serverError} />}
        <Button variant="primary" type="submit" disabled={form.creating}>
          {form.creating ? "Creating..." : "Create owner account"}
        </Button>
      </form>
    </AuthCard>
  );
}
