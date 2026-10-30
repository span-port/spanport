import "./styles/tokens.css";
import "./styles/app.css";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { ApiError } from "./api/client";
import { App } from "./App";
import {
  CURRENT_USER_QUERY_KEY,
  FIRST_SERVER_ERROR_STATUS,
  MAX_QUERY_RETRIES,
  QUERY_STALE_MS,
  STATUS_UNAUTHORIZED,
} from "./constants/api";
import { ROOT_ELEMENT_ID } from "./constants/ui";

/** Any 401 means the session ended (signed out elsewhere, idle, reset): show Sign in. */
function signOutOnUnauthorized(error: Error): void {
  if (error instanceof ApiError && error.status === STATUS_UNAUTHORIZED) {
    queryClient.setQueryData([CURRENT_USER_QUERY_KEY], null);
  }
}

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: signOutOnUnauthorized }),
  mutationCache: new MutationCache({ onError: signOutOnUnauthorized }),
  defaultOptions: {
    queries: {
      staleTime: QUERY_STALE_MS,
      // A 4xx (signed out, bad query) fails the same way every time, so only retry the rest.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status < FIRST_SERVER_ERROR_STATUS) &&
        failureCount < MAX_QUERY_RETRIES,
    },
  },
});

const rootElement = document.getElementById(ROOT_ELEMENT_ID);
if (!rootElement) throw new Error(`index.html has no #${ROOT_ELEMENT_ID} element`);

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
