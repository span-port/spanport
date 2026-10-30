import { ApiError } from "../../api/client";
import { UNREACHABLE_SERVER_MESSAGE } from "../../constants/ui";

interface ErrorBannerProps {
  error: unknown;
}

/** Explain a failed request in plain words, with the request ID for support when there is one. */
export function ErrorBanner({ error }: ErrorBannerProps) {
  if (!(error instanceof ApiError)) {
    return (
      <div className="banner banner-error" role="alert">
        {UNREACHABLE_SERVER_MESSAGE}
      </div>
    );
  }
  return (
    <div className="banner banner-error" role="alert">
      <strong>{error.title}.</strong> {error.detail}
      {error.requestId && <span className="banner-meta">Request ID {error.requestId}</span>}
    </div>
  );
}
