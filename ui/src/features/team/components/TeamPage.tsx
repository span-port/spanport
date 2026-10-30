import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { CANCEL_INVITE_CONFIRM_LABEL } from "../../../constants/team";
import { formatRangeTime } from "../../../lib/formatTime";
import { canChangeUser, projectAccessLabel, roleLabel, rolesYouCanGive } from "../../../lib/team";
import { useSessionStore } from "../../../state/sessionStore";
import { useCurrentUser } from "../../auth";
import { useProjects, type ProjectItem } from "../../projects";
import type { PendingInvite } from "../api";
import { useInviteForm, useTeam } from "../hooks/useTeam";
import { InviteForm } from "./InviteForm";
import { UserRow } from "./UserRow";

/** Users: who is in the organization, which projects they see, pending invites, and inviting. */
export function TeamPage() {
  const you = useCurrentUser().data ?? undefined;
  const team = useTeam();
  const projects = useProjects().data?.data ?? [];
  const form = useInviteForm(window.location.origin);
  const timeZone = useSessionStore((session) => session.timeZone);
  const roles = rolesYouCanGive(you?.role);
  return (
    <div className="setup-page">
      <header className="page-heading">
        <h1 className="page-title">Users</h1>
        <p className="text-secondary">
          Invite people by email with a role. They get access only after opening the invite link and pressing
          Accept. Members and viewers can be limited to some projects; owners and admins see every project.
        </p>
      </header>
      {team.error && <ErrorBanner error={team.error} />}
      <InviteForm form={form} roles={roles} projects={projects} />
      <div className="panel panel-table">
        <table className="key-table">
          <caption className="panel-title">People · {team.users.length}</caption>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Projects</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {team.users.map((user) => (
              <UserRow
                key={user.id}
                user={user}
                editable={canChangeUser(you, user)}
                roles={roles}
                projects={projects}
                onRole={team.changeRole}
                onProjects={team.setAccess}
                onRemove={team.remove}
              />
            ))}
          </tbody>
        </table>
      </div>
      {team.invites.length > 0 && (
        <div className="panel panel-table">
          <table className="key-table">
            <caption className="panel-title">Waiting to accept · {team.invites.length}</caption>
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Projects</th>
                <th>Invited by</th>
                <th>Link expires</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {team.invites.map((invite) => (
                <InviteRow
                  key={invite.id}
                  invite={invite}
                  projects={projects}
                  timeZone={timeZone}
                  onCancel={team.cancel}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface InviteRowProps {
  invite: PendingInvite;
  projects: ProjectItem[];
  timeZone: string;
  onCancel: (inviteId: string) => void;
}

/** One pending invite; cancel needs a second click. */
function InviteRow({ invite, projects, timeZone, onCancel }: InviteRowProps) {
  const [confirming, setConfirming] = useState(false);
  return (
    <tr>
      <td>{invite.email}</td>
      <td>{roleLabel(invite.role)}</td>
      <td className="text-sm">{projectAccessLabel(invite, projects)}</td>
      <td>{invite.invited_by ?? "Removed user"}</td>
      <td className="mono">{formatRangeTime(Date.parse(invite.expires_at), timeZone)}</td>
      <td className="cell-actions">
        <Button
          className="button-small button-danger-text"
          onClick={() => {
            if (confirming) onCancel(invite.id);
            else setConfirming(true);
          }}
        >
          {confirming ? CANCEL_INVITE_CONFIRM_LABEL : "Cancel invite"}
        </Button>
      </td>
    </tr>
  );
}
