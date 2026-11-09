// Whether the page is open somewhere the browser will keep Spanport's Secure sign-in cookies.
import { LOCAL_HOSTNAMES, PLAIN_HTTP_PROTOCOL } from "../constants/auth";

/**
 * Whether signing in can't work here: the page is on plain http and not on this machine's
 * own address (browsers keep Secure cookies over http only for localhost).
 *
 * @param protocol - `location.protocol`, e.g. "http:".
 * @param hostname - `location.hostname`, e.g. "spanport.acme.com".
 * @returns True when the page should be opened over https:// instead.
 */
export function needsHttps(protocol: string, hostname: string): boolean {
  return protocol === PLAIN_HTTP_PROTOCOL && !LOCAL_HOSTNAMES.includes(hostname.toLowerCase());
}
