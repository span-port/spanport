import type { ReactNode } from "react";

import { BrandMark } from "../../../components/ui/BrandMark";

/** The centred card the Sign in and Set up pages share. */
export function AuthCard({ children }: { children: ReactNode }) {
  return (
    <main className="auth-page">
      <div className="auth-card">
        <BrandMark />
        {children}
      </div>
    </main>
  );
}
