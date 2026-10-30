/** URL helpers shared by the exporter and the key check. */

import { ALLOWED_URL_PROTOCOLS } from "./constants.js";

/**
 * Append a path to a base URL, keeping any path the base already has (e.g. behind a proxy).
 *
 * @param baseUrl - e.g. "https://example.com/spanport" or "https://example.com/spanport/".
 * @param path - Starting with "/", e.g. "/v1/logs".
 * @returns The joined URL text.
 */
export function joinUrl(baseUrl: string, path: string): string {
  return (baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl) + path;
}

/**
 * Whether the text is an absolute http:// or https:// URL.
 *
 * @param url - The URL text to check.
 * @returns True only for parseable http(s) URLs.
 */
export function isHttpUrl(url: string): boolean {
  return URL.canParse(url) && ALLOWED_URL_PROTOCOLS.includes(new URL(url).protocol);
}
