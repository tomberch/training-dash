import { useState, useEffect, useCallback } from "react";

export type Theme = "latte" | "mocha" | "system";

const THEME_STORAGE_KEY = "traindash-theme";

/**
 * Get the system's preferred color scheme
 */
function getSystemTheme(): "latte" | "mocha" {
  if (typeof window === "undefined") return "latte";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "mocha"
    : "latte";
}

/**
 * Apply a theme to the document
 */
function applyTheme(theme: "latte" | "mocha") {
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  
  // Also set .dark class for Tailwind's dark: variant
  if (theme === "mocha") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

/**
 * Hook for managing theme state.
 * 
 * - Persists preference to localStorage
 * - Supports "system" to follow OS preference
 * - Applies theme via data-theme attribute on <html>
 * 
 * @example
 * ```tsx
 * const { theme, setTheme, resolvedTheme } = useTheme();
 * 
 * // Toggle between light and dark
 * <button onClick={() => setTheme(resolvedTheme === "latte" ? "mocha" : "latte")}>
 *   Toggle theme
 * </button>
 * 
 * // Follow system preference
 * <button onClick={() => setTheme("system")}>
 *   Use system theme
 * </button>
 * ```
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return "system";
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "latte" || stored === "mocha" || stored === "system") {
      return stored;
    }
    return "system";
  });

  // The actual theme being displayed (resolves "system" to latte/mocha)
  const [resolvedTheme, setResolvedTheme] = useState<"latte" | "mocha">(() => {
    if (theme === "system") return getSystemTheme();
    return theme;
  });

  // Apply theme when it changes
  useEffect(() => {
    const resolved = theme === "system" ? getSystemTheme() : theme;
    setResolvedTheme(resolved);
    applyTheme(resolved);
  }, [theme]);

  // Listen for system theme changes when in "system" mode
  useEffect(() => {
    if (theme !== "system") return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      const newTheme = e.matches ? "mocha" : "latte";
      setResolvedTheme(newTheme);
      applyTheme(newTheme);
    };

    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, [theme]);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem(THEME_STORAGE_KEY, newTheme);
  }, []);

  return {
    /** The user's preference: "latte", "mocha", or "system" */
    theme,
    /** Set the theme preference */
    setTheme,
    /** The actual theme being displayed (never "system") */
    resolvedTheme,
  };
}
