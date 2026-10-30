import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** "primary" for the main action on a screen (teal), "secondary" for everything else. */
  variant?: "primary" | "secondary";
}

/** A button with the design system's look. Defaults to type="button" so it never submits by accident. */
export function Button({ variant = "secondary", type = "button", className, ...rest }: ButtonProps) {
  const classes = ["button", `button-${variant}`, className].filter(Boolean).join(" ");
  return <button type={type} className={classes} {...rest} />;
}
