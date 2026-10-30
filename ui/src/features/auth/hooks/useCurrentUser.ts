// Who is signed in, as the server says. Null means show Sign in.
import { useQuery } from "@tanstack/react-query";

import { CURRENT_USER_QUERY_KEY } from "../../../constants/api";
import { fetchCurrentUser } from "../api";

/** The signed-in person (null when signed out); rechecked when the tab regains focus. */
export function useCurrentUser() {
  return useQuery({
    queryKey: [CURRENT_USER_QUERY_KEY],
    queryFn: ({ signal }) => fetchCurrentUser(signal),
  });
}
