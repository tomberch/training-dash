import { useState, useEffect, useCallback, useRef } from "react";

/** LocalStorage key prefix for map size persistence */
const STORAGE_KEY_PREFIX = "map-size-";

interface UseResizableMapOptions {
  /** Unique key for localStorage persistence */
  storageKey: string;
  /** Default height in pixels */
  defaultHeight: number;
  /** Minimum height in pixels */
  minHeight: number;
  /** Maximum height in pixels */
  maxHeight: number;
  /** Default width as percentage (for split-pane mode) */
  defaultWidthPercent: number;
  /** Minimum width percentage */
  minWidthPercent: number;
  /** Maximum width percentage */
  maxWidthPercent: number;
}

interface UseResizableMapResult {
  height: number;
  widthPercent: number;
  isResizing: boolean;
  startResizeHeight: (e: React.MouseEvent) => void;
  startResizeWidth: (e: React.MouseEvent) => void;
}

export function useResizableMap({
  storageKey,
  defaultHeight,
  minHeight,
  maxHeight,
  defaultWidthPercent,
  minWidthPercent,
  maxWidthPercent,
}: UseResizableMapOptions): UseResizableMapResult {
  // Load initial values from localStorage
  const [height, setHeight] = useState(() => {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${storageKey}-height`);
    if (stored) {
      const val = parseInt(stored, 10);
      if (!isNaN(val) && val >= minHeight && val <= maxHeight) {
        return val;
      }
    }
    return defaultHeight;
  });

  const [widthPercent, setWidthPercent] = useState(() => {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${storageKey}-width`);
    if (stored) {
      const val = parseInt(stored, 10);
      if (!isNaN(val) && val >= minWidthPercent && val <= maxWidthPercent) {
        return val;
      }
    }
    return defaultWidthPercent;
  });

  const [isResizing, setIsResizing] = useState(false);
  const resizeMode = useRef<"height" | "width" | null>(null);
  const startY = useRef(0);
  const startX = useRef(0);
  const startValue = useRef(0);
  const containerWidth = useRef(0);

  // Persist to localStorage when values change
  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${storageKey}-height`, String(height));
  }, [storageKey, height]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${storageKey}-width`, String(widthPercent));
  }, [storageKey, widthPercent]);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;

      if (resizeMode.current === "height") {
        const deltaY = e.clientY - startY.current;
        const newHeight = Math.min(maxHeight, Math.max(minHeight, startValue.current + deltaY));
        setHeight(newHeight);
      } else if (resizeMode.current === "width") {
        const deltaX = e.clientX - startX.current;
        const deltaPercent = (deltaX / containerWidth.current) * 100;
        const newPercent = Math.min(
          maxWidthPercent,
          Math.max(minWidthPercent, startValue.current + deltaPercent)
        );
        setWidthPercent(Math.round(newPercent));
      }
    },
    [isResizing, minHeight, maxHeight, minWidthPercent, maxWidthPercent]
  );

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
    resizeMode.current = null;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, []);

  useEffect(() => {
    if (isResizing) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      return () => {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [isResizing, handleMouseMove, handleMouseUp]);

  const startResizeHeight = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      resizeMode.current = "height";
      startY.current = e.clientY;
      startValue.current = height;
      setIsResizing(true);
      document.body.style.cursor = "ns-resize";
      document.body.style.userSelect = "none";
    },
    [height]
  );

  const startResizeWidth = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      resizeMode.current = "width";
      startX.current = e.clientX;
      startValue.current = widthPercent;
      // Get container width for percentage calculation
      const container = (e.target as HTMLElement).closest("[data-resize-container]");
      containerWidth.current = container?.clientWidth || window.innerWidth;
      setIsResizing(true);
      document.body.style.cursor = "ew-resize";
      document.body.style.userSelect = "none";
    },
    [widthPercent]
  );

  return {
    height,
    widthPercent,
    isResizing,
    startResizeHeight,
    startResizeWidth,
  };
}
