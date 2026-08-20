import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export type SettingsTab = "profile" | "preferences" | "training" | "connections" | "gear";

const VALID_TABS: SettingsTab[] = ["profile", "preferences", "training", "connections", "gear"];
const STORAGE_KEY = "settings-tab";
const DEFAULT_TAB: SettingsTab = "profile";

function isValidTab(value: string | null): value is SettingsTab {
  return value !== null && VALID_TABS.includes(value as SettingsTab);
}

/**
 * Hook for managing Settings tab state with URL hash and localStorage persistence.
 * 
 * Priority:
 * 1. URL hash (e.g., /settings#preferences)
 * 2. localStorage (remembers last visited tab)
 * 3. Default to "profile"
 */
export function useSettingsTabs() {
  const location = useLocation();
  const navigate = useNavigate();

  // Initialize from URL hash or localStorage
  const getInitialTab = useCallback((): SettingsTab => {
    // Check URL hash first
    const hash = location.hash.replace("#", "");
    if (isValidTab(hash)) {
      return hash;
    }

    // Fall back to localStorage
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isValidTab(stored)) {
      return stored;
    }

    return DEFAULT_TAB;
  }, [location.hash]);

  const [activeTab, setActiveTabState] = useState<SettingsTab>(getInitialTab);

  // Sync with URL hash changes (e.g., browser back/forward)
  useEffect(() => {
    const hash = location.hash.replace("#", "");
    if (isValidTab(hash) && hash !== activeTab) {
      setActiveTabState(hash);
    }
  }, [location.hash, activeTab]);

  // Set tab and persist to both URL and localStorage
  const setActiveTab = useCallback(
    (tab: SettingsTab) => {
      setActiveTabState(tab);
      localStorage.setItem(STORAGE_KEY, tab);
      
      // Update URL hash without triggering navigation
      navigate(`${location.pathname}#${tab}`, { replace: true });
    },
    [navigate, location.pathname]
  );

  // On mount, sync URL to match the active tab if no hash present
  useEffect(() => {
    const hash = location.hash.replace("#", "");
    if (!hash && activeTab !== DEFAULT_TAB) {
      navigate(`${location.pathname}#${activeTab}`, { replace: true });
    } else if (!hash) {
      // Set default tab in URL
      navigate(`${location.pathname}#${DEFAULT_TAB}`, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    activeTab,
    setActiveTab,
    tabs: VALID_TABS,
  };
}
