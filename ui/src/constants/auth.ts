// Sign in and first-time setup.

// Matches the server's rule; the strength meter asks for more.
export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 256;
export const MAX_NAME_LENGTH = 200;
export const MAX_ORG_NAME_LENGTH = 63;
export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// A strong password is long and mixes at least this many kinds of character.
export const STRONG_PASSWORD_KINDS = 3;
export const PASSWORD_KIND_PATTERNS = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/];

export const EMAIL_MESSAGE = "Enter a valid email address.";
export const NAME_MESSAGE = "Enter your name.";
export const ORG_MESSAGE = "Enter your organization's name.";
export const PASSWORD_REQUIRED_MESSAGE = "Enter your password.";
export const WEAK_PASSWORD_MESSAGE = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
export const SETUP_TOKEN_MESSAGE = "Paste the setup token from the server's log.";
export const MAX_SETUP_TOKEN_LENGTH = 200;
export const SETUP_TOKEN_COMMAND = "docker compose logs server | grep setup_token";
export const RESET_PASSWORD_COMMAND =
  "docker compose exec server python -m spanport_server.cli reset-password --email <email>";
