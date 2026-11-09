/** Where the data key may be sent: which server checks it, and warnings for plain http. */

import { DEFAULT_SERVER_URL, LOCAL_HOSTNAMES, PLAIN_HTTP_PROTOCOL } from "./constants.js";
import { sdkWarning } from "./sdkMessages.js";
import { isHttpUrl } from "./urls.js";

/**
 * Whether the URL points at this machine (localhost, 127.0.0.1 or [::1]).
 *
 * @param url - An http(s) URL.
 * @returns False for other hosts and for text that isn't a URL.
 */
export function isLocalUrl(url: string): boolean {
  return URL.canParse(url) && LOCAL_HOSTNAMES.includes(new URL(url).hostname);
}

/**
 * The server to check the data key with, or undefined to skip the check (with a note on stderr).
 *
 * Without a `serverUrl`, the default (localhost) is used only when the collector is local too;
 * otherwise the key would be sent to whatever answers on this machine, which may be the app.
 *
 * @param collectorUrl - Where logs and traces are sent.
 * @param serverUrl - The `serverUrl` option, if given.
 * @returns The URL to check the key with, or undefined.
 */
export function keyCheckUrl(collectorUrl: string, serverUrl: string | undefined): string | undefined {
  if (serverUrl !== undefined) return serverUrl;
  if (isLocalUrl(collectorUrl)) return DEFAULT_SERVER_URL;
  sdkWarning(
    "data key not checked: set serverUrl to your Spanport address (the UI's URL, " +
      "e.g. https://spanport.example.com; it forwards /api to the server)",
  );
  return undefined;
}

/**
 * Say once on stderr if the data key would go over plain http to another machine.
 *
 * @param urls - Every URL the data key is sent to.
 */
export function warnPlainHttp(urls: string[]): void {
  const exposed = urls.filter(
    (url) => isHttpUrl(url) && new URL(url).protocol === PLAIN_HTTP_PROTOCOL && !isLocalUrl(url),
  );
  if (exposed.length === 0) return;
  sdkWarning(
    `the data key is sent over plain http to ${exposed.join(", ")}; anyone on the network can ` +
      "read it. Use https://",
  );
}
