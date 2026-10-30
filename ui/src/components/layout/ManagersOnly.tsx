import type { ReactNode } from "react";

import { MANAGERS_ONLY_NOTE } from "../../constants/ui";
import type { Role } from "../../features/auth/api";
import { isManager } from "../../lib/roles";

interface ManagersOnlyProps {
  role: Role;
  title: string;
  children: ReactNode;
}

/**
 * The screen for owners and admins; for anyone else (who reached it by URL), a short note
 * instead of forms the server would refuse.
 */
export function ManagersOnly({ role, title, children }: ManagersOnlyProps) {
  if (isManager(role)) return children;
  return (
    <div className="setup-page">
      <header className="page-heading">
        <h1 className="page-title">{title}</h1>
        <p className="text-secondary">{MANAGERS_ONLY_NOTE}</p>
      </header>
    </div>
  );
}
