import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Hook for lazy-loading sections using Intersection Observer.
 * Returns a ref callback to attach to a sentinel element and a boolean indicating
 * whether the section has entered the viewport.
 */
export function useLazySection(options?: IntersectionObserverInit) {
  const [hasEntered, setHasEntered] = useState(false);
  const hasEnteredRef = useRef(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
  }, []);

  // Use a callback ref so we observe immediately when the element mounts
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      // Cleanup any existing observer
      cleanup();

      // Skip if already triggered or no node
      if (hasEnteredRef.current || !node) {
        return;
      }

      const observer = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting && !hasEnteredRef.current) {
            hasEnteredRef.current = true;
            setHasEntered(true);
            observer.disconnect();
          }
        },
        {
          root: null,
          rootMargin: "200px",
          threshold: 0,
          ...options,
        }
      );

      observer.observe(node);
      observerRef.current = observer;
    },
    [cleanup, options]
  );

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  return { sentinelRef, hasEntered };
}
