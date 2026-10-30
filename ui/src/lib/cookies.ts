// Read cookies the server meant the UI to read (only the CSRF token; the session is HttpOnly).
import { COOKIE_SEPARATOR, NAME_VALUE_SEPARATOR } from "../constants/api";

/** The value of cookie `name` in `cookieHeader` (document.cookie), or null. */
export function readCookie(name: string, cookieHeader: string = document.cookie): string | null {
  for (const pair of cookieHeader.split(COOKIE_SEPARATOR)) {
    const separatorAt = pair.indexOf(NAME_VALUE_SEPARATOR);
    if (separatorAt > 0 && pair.slice(0, separatorAt) === name) {
      return decodeURIComponent(pair.slice(separatorAt + 1));
    }
  }
  return null;
}
