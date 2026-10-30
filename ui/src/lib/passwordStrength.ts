// How strong a new password looks, for the meter under the password box.
import {
  MIN_PASSWORD_LENGTH,
  PASSWORD_KIND_PATTERNS,
  STRONG_PASSWORD_KINDS,
} from "../constants/auth";

export type PasswordStrength = "empty" | "weak" | "strong";

/** Strong means long enough and mixing lower case, upper case, digits or symbols. */
export function passwordStrength(password: string): PasswordStrength {
  if (password === "") return "empty";
  return password.length >= MIN_PASSWORD_LENGTH && characterKinds(password) >= STRONG_PASSWORD_KINDS
    ? "strong"
    : "weak";
}

/** How full the meter is, from 0 to 1: one step for length and one per kind of character. */
export function strengthFill(password: string): number {
  if (password === "") return 0;
  const steps = (password.length >= MIN_PASSWORD_LENGTH ? 1 : 0) + characterKinds(password);
  return steps / (PASSWORD_KIND_PATTERNS.length + 1);
}

/** What the meter says. */
export function strengthMessage(strength: PasswordStrength): string {
  switch (strength) {
    case "empty":
      return `At least ${MIN_PASSWORD_LENGTH} characters`;
    case "weak":
      return `Use ${MIN_PASSWORD_LENGTH}+ characters with a mix of letters, numbers and symbols`;
    case "strong":
      return "Strong password";
  }
}

function characterKinds(password: string): number {
  return PASSWORD_KIND_PATTERNS.filter((pattern) => pattern.test(password)).length;
}
