/**
 * Checks the data key once against the Spanport server and says clearly if it is wrong.
 *
 * The collector accepts logs without checking keys, so without this an app with a wrong key would
 * lose its logs silently.
 */

import {
  AUTHORIZATION_HEADER,
  BEARER_PREFIX,
  CURRENT_API_KEY_PATH,
  HTTP_UNAUTHORIZED,
  KEY_CHECK_TIMEOUT_MS,
  VISIBLE_KEY_SUFFIX_LENGTH,
} from "./constants.js";
import { sdkError, sdkInfo, sdkWarning } from "./sdkMessages.js";
import { isHttpUrl, joinUrl } from "./urls.js";

/**
 * Ask the server whether the data key is valid and report the answer on stderr. Never throws.
 *
 * Redirects are refused: following one would send the key to whatever host it names.
 *
 * @param serverUrl - Base URL of the Spanport server.
 * @param dataKey - The raw data key; only its last characters are ever printed.
 * @returns True if the server accepted the key; false if it rejected it or could not be asked.
 */
export async function checkDataKey(serverUrl: string, dataKey: string): Promise<boolean> {
  const keySuffix = dataKey.slice(-VISIBLE_KEY_SUFFIX_LENGTH);
  if (!isHttpUrl(serverUrl)) {
    sdkWarning("serverUrl must start with http:// or https://; key not checked");
    return false;
  }
  try {
    const response = await fetch(joinUrl(serverUrl, CURRENT_API_KEY_PATH), {
      headers: { [AUTHORIZATION_HEADER]: BEARER_PREFIX + dataKey },
      redirect: "manual",
      signal: AbortSignal.timeout(KEY_CHECK_TIMEOUT_MS),
    });
    // The body isn't needed; release the connection.
    await response.body?.cancel();
    return reportAnswer(response.status, response.ok, serverUrl, keySuffix);
  } catch (error) {
    sdkWarning(
      `could not reach ${serverUrl} to check data key ...${keySuffix}: ${describe(error)}`,
    );
    return false;
  }
}

function reportAnswer(status: number, ok: boolean, serverUrl: string, keySuffix: string): boolean {
  if (ok) {
    sdkInfo(`data key ...${keySuffix} accepted`);
    return true;
  }
  if (status === HTTP_UNAUTHORIZED) {
    sdkError(
      `data key ...${keySuffix} was rejected by ${serverUrl}; logs will NOT be stored. ` +
        "Check the key, or create one with create-data-key.",
    );
    return false;
  }
  sdkWarning(`could not check data key ...${keySuffix}: HTTP ${String(status)}`);
  return false;
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
