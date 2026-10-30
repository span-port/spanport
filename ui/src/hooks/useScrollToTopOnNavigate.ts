// Open each screen at its top, not wherever the previous screen was scrolled to.
import { useEffect } from "react";
import { useLocation } from "react-router";

/** Scroll the window to the top whenever the path changes (filters in the URL don't count). */
export function useScrollToTopOnNavigate(): void {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
}
