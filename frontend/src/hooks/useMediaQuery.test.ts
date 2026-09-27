import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMediaQuery, useIsWideScreen } from "./useMediaQuery";

describe("useMediaQuery", () => {
  let originalMatchMedia: typeof window.matchMedia;
  let mediaQueryListeners: Map<string, Array<(e: MediaQueryListEvent) => void>>;

  const createMockMediaQuery = (query: string, initialMatches: boolean) => ({
    matches: initialMatches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_, handler: EventListener) => {
      const listeners = mediaQueryListeners.get(query) ?? [];
      listeners.push(handler as (e: MediaQueryListEvent) => void);
      mediaQueryListeners.set(query, listeners);
    }),
    removeEventListener: vi.fn((_, handler: EventListener) => {
      const listeners = mediaQueryListeners.get(query) ?? [];
      const index = listeners.indexOf(handler as (e: MediaQueryListEvent) => void);
      if (index > -1) listeners.splice(index, 1);
    }),
    dispatchEvent: vi.fn(),
  });

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
    mediaQueryListeners = new Map();
  });

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  describe("useMediaQuery", () => {
    it("returns initial match state", () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => createMockMediaQuery(query, true),
      });

      const { result } = renderHook(() => useMediaQuery("(min-width: 1024px)"));
      expect(result.current).toBe(true);
    });

    it("returns false when query does not match", () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => createMockMediaQuery(query, false),
      });

      const { result } = renderHook(() => useMediaQuery("(min-width: 1024px)"));
      expect(result.current).toBe(false);
    });

    it("updates when media query match changes", () => {
      let currentMatches = false;

      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => {
          const mock = createMockMediaQuery(query, currentMatches);
          // Override matches to be dynamic
          Object.defineProperty(mock, "matches", {
            get: () => currentMatches,
          });
          return mock;
        },
      });

      const { result } = renderHook(() => useMediaQuery("(min-width: 1024px)"));
      expect(result.current).toBe(false);

      // Simulate media query change
      act(() => {
        currentMatches = true;
        const listeners = mediaQueryListeners.get("(min-width: 1024px)") ?? [];
        listeners.forEach((listener) => {
          listener({ matches: true } as MediaQueryListEvent);
        });
      });

      expect(result.current).toBe(true);
    });

    it("cleans up event listener on unmount", () => {
      const mockRemoveEventListener = vi.fn();

      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => ({
          ...createMockMediaQuery(query, false),
          removeEventListener: mockRemoveEventListener,
        }),
      });

      const { unmount } = renderHook(() => useMediaQuery("(min-width: 1024px)"));

      unmount();

      expect(mockRemoveEventListener).toHaveBeenCalledWith(
        "change",
        expect.any(Function)
      );
    });

    it("handles different query strings", () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => {
          // Different queries return different results
          if (query === "(min-width: 768px)") {
            return createMockMediaQuery(query, true);
          }
          return createMockMediaQuery(query, false);
        },
      });

      const { result: result1 } = renderHook(() =>
        useMediaQuery("(min-width: 768px)")
      );
      const { result: result2 } = renderHook(() =>
        useMediaQuery("(min-width: 1024px)")
      );

      expect(result1.current).toBe(true);
      expect(result2.current).toBe(false);
    });

    it("re-evaluates when query changes", () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => {
          if (query === "(min-width: 768px)") {
            return createMockMediaQuery(query, true);
          }
          return createMockMediaQuery(query, false);
        },
      });

      const { result, rerender } = renderHook(
        ({ query }) => useMediaQuery(query),
        { initialProps: { query: "(min-width: 768px)" } }
      );

      expect(result.current).toBe(true);

      rerender({ query: "(min-width: 1024px)" });

      expect(result.current).toBe(false);
    });
  });

  describe("useIsWideScreen", () => {
    it("returns true when screen is at least 1280px", () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => {
          if (query === "(min-width: 1280px)") {
            return createMockMediaQuery(query, true);
          }
          return createMockMediaQuery(query, false);
        },
      });

      const { result } = renderHook(() => useIsWideScreen());
      expect(result.current).toBe(true);
    });

    it("returns false when screen is narrower than 1280px", () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => createMockMediaQuery(query, false),
      });

      const { result } = renderHook(() => useIsWideScreen());
      expect(result.current).toBe(false);
    });

    it("uses the correct breakpoint query", () => {
      const mockMatchMedia = vi.fn((query: string) =>
        createMockMediaQuery(query, false)
      );

      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: mockMatchMedia,
      });

      renderHook(() => useIsWideScreen());

      expect(mockMatchMedia).toHaveBeenCalledWith("(min-width: 1280px)");
    });
  });
});
