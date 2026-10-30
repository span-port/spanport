// The one small global store: this browser tab's display settings (the timezone, UTC by default).
// Sign-in state is not here: it comes from the server (/api/v1/auth/me) through TanStack Query.
import { create } from "zustand";

import { UTC_ZONE } from "../constants/ui";

interface SessionState {
  timeZone: string;
  setTimeZone: (timeZone: string) => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  timeZone: UTC_ZONE,
  setTimeZone: (timeZone) => {
    set({ timeZone });
  },
}));
