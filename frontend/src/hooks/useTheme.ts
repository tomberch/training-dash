import { useState, useEffect, useCallback } from "react";

export type Theme = "latte" | "mocha" | "midnight" | "system";
export type ResolvedTheme = "latte" | "mocha" | "midnight";

const THEME_STORAGE_KEY = "traindash-theme";

/**
 * Get the system's preferred color scheme
 * When system preference is dark, defaults to midnight (the new dark theme)
 */
function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "latte";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "midnight"
    : "latte";
}

/**
 * Apply a theme to the document
 */
function applyTheme(theme: ResolvedTheme) {
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  
  // Also set .dark class for Tailwind's dark: variant (both mocha and midnight are dark)
  if (theme === "mocha" || theme === "midnight") {
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
 * // Toggle between themes
 * <button onClick={() => setTheme("midnight")}>
 *   Use Midnight theme
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
    if (stored === "latte" || stored === "mocha" || stored === "midnight" || stored === "system") {
      return stored;
    }
    return "system";
  });

  // The actual theme being displayed (resolves "system" to latte/mocha/midnight)
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => {
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
      const newTheme: ResolvedTheme = e.matches ? "midnight" : "latte";
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
