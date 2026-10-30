// What happens once the server has set the session cookies.
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { CURRENT_USER_QUERY_KEY } from "../../../constants/api";
import { LOGIN_ROUTE, LOGS_ROUTE } from "../../../constants/ui";
import type { CurrentUser } from "../api";

/**
 * Handlers for signing in and out.
 *
 * Cached data is cleared both ways, so nothing from one person's session shows in the next.
 */
export function useSignedIn() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return {
    enter: (user: CurrentUser) => {
      queryClient.clear();
      queryClient.setQueryData([CURRENT_USER_QUERY_KEY], user);
      void navigate(LOGS_ROUTE, { replace: true });
    },
    leave: () => {
      queryClient.clear();
      queryClient.setQueryData([CURRENT_USER_QUERY_KEY], null);
      void navigate(LOGIN_ROUTE, { replace: true });
    },
  };
}
