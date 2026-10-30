// Sign out: end the session on the server, then show Sign in.
import { useMutation } from "@tanstack/react-query";

import { signOut } from "../api";
import { useSignedIn } from "./useSignedIn";

/** `signOut()` ends the session; the UI leaves even if the server can't be reached. */
export function useSignOut() {
  const signedIn = useSignedIn();
  const mutation = useMutation({ mutationFn: signOut, onSettled: signedIn.leave });
  return {
    signOut: () => {
      mutation.mutate();
    },
    signingOut: mutation.isPending,
  };
}
