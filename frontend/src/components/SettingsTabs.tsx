import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import type { SettingsTab } from "@/hooks/useSettingsTabs";

interface TabConfig {
  id: SettingsTab;
  label: string;
  icon: React.ReactNode;
  isLink?: boolean;
  href?: string;
}

const TABS: TabConfig[] = [
  {
    id: "profile",
    label: "Profile",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    ),
  },
  {
    id: "preferences",
    label: "Preferences",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    ),
  },
  {
    id: "training",
    label: "Training",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },

  {
    id: "connections",
    label: "Connections",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
      </svg>
    ),
  },
];

interface SettingsTabsProps {
  activeTab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
}

export function SettingsTabs({ activeTab, onTabChange }: SettingsTabsProps) {
  const navigate = useNavigate();
  
  const handleTabClick = (tab: TabConfig) => {
    if (tab.isLink && tab.href) {
      navigate(tab.href);
    } else {
      onTabChange(tab.id);
    }
  };

  return (
    <div className="mb-8 border-b border-border overflow-x-auto">
      <div className="flex gap-6 md:gap-8 min-w-max">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab)}
            className={cn(
              "pb-3 px-1 text-sm font-medium transition-colors border-b-2 -mb-px",
              activeTab === tab.id
                ? "text-primary border-primary"
                : "text-muted-foreground border-transparent hover:text-foreground"
            )}
            aria-selected={activeTab === tab.id}
            role="tab"
          >
            <div className="flex items-center gap-2">
              {tab.icon}
              {tab.label}
              {tab.isLink && (
                <svg className="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

interface SettingsTabPanelProps {
  id: SettingsTab;
  activeTab: SettingsTab;
  children: React.ReactNode;
}

export function SettingsTabPanel({ id, activeTab, children }: SettingsTabPanelProps) {
  if (id !== activeTab) return null;

  return (
    <div
      role="tabpanel"
      aria-labelledby={`tab-${id}`}
      className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200"
    >
      {children}
    </div>
  );
}
