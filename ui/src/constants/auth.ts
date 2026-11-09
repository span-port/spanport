// Sign in and first-time setup.

// Matches the server's rule; the strength meter asks for more.
export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 256;
export const MAX_NAME_LENGTH = 200;
export const MAX_ORG_NAME_LENGTH = 63;
// One plain address, the same rule as the server's: no separators, quotes, brackets or
// control characters, so one value can never become several recipients.
// eslint-disable-next-line no-control-regex -- control characters are exactly what it refuses
export const EMAIL_PATTERN = /^[^\s@,;:<>()[\]"\\\x00-\x1f\x7f]+@[^\s@,;:<>()[\]"\\\x00-\x1f\x7f]+\.[^\s@,;:<>()[\]"\\\x00-\x1f\x7f]+$/;// A strong password is long and mixes at least this many kinds of character.
export const STRONG_PASSWORD_KINDS = 3;
export const PASSWORD_KIND_PATTERNS = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/];

export const EMAIL_MESSAGE = "Enter a valid email address.";
export const NAME_MESSAGE = "Enter your name.";
export const ORG_MESSAGE = "Enter your organization's name.";
export const PASSWORD_REQUIRED_MESSAGE = "Enter your password.";
export const WEAK_PASSWORD_MESSAGE = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
// Sign-in cookies are Secure (__Host-), so browsers keep them only over HTTPS or on this
// machine's own addresses.
export const PLAIN_HTTP_PROTOCOL = "http:";
export const LOCAL_HOSTNAMES = ["localhost", "127.0.0.1", "[::1]", "::1"];
export const HTTPS_NEEDED_MESSAGE =
  "Spanport needs HTTPS. Open it over https:// (or on localhost): over plain http the browser drops the sign-in cookie, so signing in can't work.";
export const SETUP_TOKEN_MESSAGE ="Paste the setup token from the server's log.";
export const MAX_SETUP_TOKEN_LENGTH = 200;
export const SETUP_TOKEN_COMMAND = "docker compose logs server | grep setup_token";
export const RESET_PASSWORD_COMMAND =
  "docker compose exec server python -m spanport_server.cli reset-password --email <email>";
