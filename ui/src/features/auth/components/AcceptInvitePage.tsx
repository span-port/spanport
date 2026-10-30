import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { MISSING_INVITE_TOKEN_MESSAGE } from "../../../constants/team";
import { roleLabel } from "../../../lib/team";
import { useAcceptInvite } from "../hooks/useAcceptInvite";
import { AuthCard } from "./AuthCard";

/**
 * The page an invite link opens: who the invite is for, and Accept. The account exists only
 * after Accept, so a link sent to the wrong person can still be cancelled before anyone joins.
 */
export function AcceptInvitePage() {
  const invite = useAcceptInvite();
  if (invite.token === null) {
    return (
      <AuthCard>
        <p role="alert" className="field-error">
          {MISSING_INVITE_TOKEN_MESSAGE}
        </p>
      </AuthCard>
    );
  }
  if (invite.details.error) {
    return (
      <AuthCard>
        <h1 className="auth-title">Invite not valid</h1>
        <ErrorBanner error={invite.details.error} />
      </AuthCard>
    );
  }
  const details = invite.details.data;
  if (!details) return <AuthCard>{null}</AuthCard>;
  return (
    <AuthCard>
      <div className="auth-heading">
        <h1 className="auth-title">Join {details.organization} on Spanport</h1>
        <p className="text-secondary">
          {details.invited_by ?? "Someone"} invited <strong>{details.email}</strong> as{" "}
          <strong>{roleLabel(details.role)}</strong>. If this isn&apos;t your email, don&apos;t accept: ask them to
          send a new invite.
        </p>
      </div>
      <form className="auth-form" noValidate onSubmit={(event) => void invite.submit(event)}>
        <label className="auth-field">
          Email
          <input className="input" type="email" value={details.email} readOnly autoComplete="username" />
        </label>
        <label className="auth-field">
          Your name
          <input className="input" type="text" autoComplete="name" {...invite.register("name")} />
        </label>
        <label className="auth-field">
          Password
          <input className="input" type="password" autoComplete="new-password" {...invite.register("password")} />
        </label>
        <div className="strength">
          <meter
            className={`strength-meter strength-${invite.strength}`}
            min={0}
            max={1}
            value={invite.strengthFill}
            aria-label="Password strength"
          />
          <span className={`strength-text strength-${invite.strength}`}>{invite.strengthMessage}</span>
        </div>
        {invite.fieldProblem && (
          <p role="alert" className="field-error">
            {invite.fieldProblem}
          </p>
        )}
        {invite.serverError && <ErrorBanner error={invite.serverError} />}
        <Button variant="primary" type="submit" disabled={invite.accepting}>
          {invite.accepting ? "Joining..." : "Accept and join"}
        </Button>
      </form>
    </AuthCard>
  );
}
