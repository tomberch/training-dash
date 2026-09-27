import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme, type Theme } from "./useTheme";

describe("useTheme", () => {
  // Store original implementations
  let originalMatchMedia: typeof window.matchMedia;
  let originalLocalStorage: Storage;

  // Mock localStorage
  const mockLocalStorage = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
      clear: vi.fn(() => {
        store = {};
      }),
      key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
      get length() {
        return Object.keys(store).length;
      },
    };
  })();

  // Mock matchMedia
  let mediaQueryMatches = false;
  let mediaQueryListeners: Array<(e: MediaQueryListEvent) => void> = [];

  const mockMatchMedia = vi.fn((query: string) => ({
    matches: mediaQueryMatches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_: string, handler: EventListener) => {
      mediaQueryListeners.push(handler as (e: MediaQueryListEvent) => void);
    }),
    removeEventListener: vi.fn((_: string, handler: EventListener) => {
      mediaQueryListeners = mediaQueryListeners.filter((h) => h !== handler);
    }),
    dispatchEvent: vi.fn(),
  }));

  beforeEach(() => {
    // Store originals
    originalMatchMedia = window.matchMedia;
    originalLocalStorage = window.localStorage;

    // Apply mocks
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: mockMatchMedia,
    });
    Object.defineProperty(window, "localStorage", {
      writable: true,
      value: mockLocalStorage,
    });

    // Reset state
    mockLocalStorage.clear();
    mediaQueryMatches = false;
    mediaQueryListeners = [];
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Restore originals
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
    Object.defineProperty(window, "localStorage", {
      writable: true,
      value: originalLocalStorage,
    });
  });

  describe("initialization", () => {
    it("defaults to system theme when no stored preference", () => {
      const { result } = renderHook(() => useTheme());
      expect(result.current.theme).toBe("system");
    });

    it("reads stored theme from localStorage", () => {
      mockLocalStorage.setItem("traindash-theme", "mocha");
      const { result } = renderHook(() => useTheme());
      expect(result.current.theme).toBe("mocha");
    });

    it("ignores invalid stored values", () => {
      mockLocalStorage.setItem("traindash-theme", "invalid-theme");
      const { result } = renderHook(() => useTheme());
      expect(result.current.theme).toBe("system");
    });

    it("resolves system theme to latte in light mode", () => {
      mediaQueryMatches = false; // Light mode
      const { result } = renderHook(() => useTheme());
      expect(result.current.resolvedTheme).toBe("latte");
    });

    it("resolves system theme to midnight in dark mode", () => {
      mediaQueryMatches = true; // Dark mode
      const { result } = renderHook(() => useTheme());
      expect(result.current.resolvedTheme).toBe("midnight");
    });
  });

  describe("setTheme", () => {
    it("updates theme to latte", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("latte");
      });

      expect(result.current.theme).toBe("latte");
      expect(result.current.resolvedTheme).toBe("latte");
    });

    it("updates theme to mocha", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("mocha");
      });

      expect(result.current.theme).toBe("mocha");
      expect(result.current.resolvedTheme).toBe("mocha");
    });

    it("updates theme to midnight", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("midnight");
      });

      expect(result.current.theme).toBe("midnight");
      expect(result.current.resolvedTheme).toBe("midnight");
    });

    it("updates theme to system and resolves based on OS preference", () => {
      mediaQueryMatches = true; // Dark mode
      const { result } = renderHook(() => useTheme());

      // First set to explicit theme
      act(() => {
        result.current.setTheme("latte");
      });
      expect(result.current.resolvedTheme).toBe("latte");

      // Then switch to system
      act(() => {
        result.current.setTheme("system");
      });
      expect(result.current.theme).toBe("system");
      expect(result.current.resolvedTheme).toBe("midnight");
    });

    it("persists theme to localStorage", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("mocha");
      });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        "traindash-theme",
        "mocha"
      );
    });
  });

  describe("DOM application", () => {
    it("sets data-theme attribute on document", () => {
      renderHook(() => useTheme());

      act(() => {
        // The hook applies theme on mount
      });

      expect(document.documentElement.getAttribute("data-theme")).toBe("latte");
    });

    it("adds dark class for mocha theme", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("mocha");
      });

      expect(document.documentElement.classList.contains("dark")).toBe(true);
    });

    it("adds dark class for midnight theme", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("midnight");
      });

      expect(document.documentElement.classList.contains("dark")).toBe(true);
    });

    it("removes dark class for latte theme", () => {
      const { result } = renderHook(() => useTheme());

      // First set dark theme
      act(() => {
        result.current.setTheme("mocha");
      });
      expect(document.documentElement.classList.contains("dark")).toBe(true);

      // Then switch to light
      act(() => {
        result.current.setTheme("latte");
      });
      expect(document.documentElement.classList.contains("dark")).toBe(false);
    });
  });

  describe("system theme changes", () => {
    it("responds to system theme changes when in system mode", () => {
      mediaQueryMatches = false; // Start in light mode
      const { result } = renderHook(() => useTheme());

      expect(result.current.resolvedTheme).toBe("latte");

      // Simulate system theme change to dark
      act(() => {
        mediaQueryListeners.forEach((listener) => {
          listener({ matches: true } as MediaQueryListEvent);
        });
      });

      expect(result.current.resolvedTheme).toBe("midnight");
    });

    it("does not respond to system changes when explicit theme is set", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("latte");
      });

      // Simulate system theme change
      act(() => {
        mediaQueryListeners.forEach((listener) => {
          listener({ matches: true } as MediaQueryListEvent);
        });
      });

      // Should remain latte, not switch to midnight
      expect(result.current.resolvedTheme).toBe("latte");
    });
  });

  describe("all theme values", () => {
    const themes: Theme[] = ["latte", "mocha", "midnight", "system"];

    themes.forEach((theme) => {
      it(`accepts ${theme} as a valid theme`, () => {
        const { result } = renderHook(() => useTheme());

        act(() => {
          result.current.setTheme(theme);
        });

        expect(result.current.theme).toBe(theme);
      });
    });

    it("resolvedTheme is never system", () => {
      const { result } = renderHook(() => useTheme());

      act(() => {
        result.current.setTheme("system");
      });

      expect(result.current.resolvedTheme).not.toBe("system");
      expect(["latte", "mocha", "midnight"]).toContain(result.current.resolvedTheme);
    });
  });
});
