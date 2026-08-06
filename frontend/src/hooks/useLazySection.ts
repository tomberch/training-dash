import { useState, useEffect, useRef } from "react";

/**
 * Hook for lazy-loading sections using Intersection Observer.
 * Returns a ref to attach to a sentinel element and a boolean indicating
 * whether the section has entered the viewport.
 */
export function useLazySection(options?: IntersectionObserverInit) {
  const [hasEntered, setHasEntered] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || hasEntered) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setHasEntered(true);
          observer.disconnect();
        }
      },
      {
        rootMargin: "200px", // Start loading 200px before entering viewport
        threshold: 0,
        ...options,
      }
    );

    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [hasEntered, options]);

  return { sentinelRef, hasEntered };
}
