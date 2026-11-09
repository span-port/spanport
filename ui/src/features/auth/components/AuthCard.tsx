import type { ReactNode } from "react";

import { BrandMark } from "../../../components/ui/BrandMark";
import { HTTPS_NEEDED_MESSAGE } from "../../../constants/auth";
import { needsHttps } from "../../../lib/secureOrigin";

/**
 * The centred card the Sign in, Set up and Accept invite pages share. Over plain http to
 * another machine it says to use https first, since signing in can't work there.
 */
export function AuthCard({ children }: { children: ReactNode }) {
  const httpsNeeded = needsHttps(window.location.protocol, window.location.hostname);
  return (
    <main className="auth-page">
      <div className="auth-card">
        <BrandMark />
        {httpsNeeded && (
          <div className="banner banner-warning" role="alert">
            {HTTPS_NEEDED_MESSAGE}
          </div>
        )}
        {children}
      </div>
    </main>
  );
}
