import { useState, useEffect, useRef, useMemo } from "react";
import type { Activity } from "../api";
import { useActivities } from "../hooks/useActivities";
import { formatDistance, formatTime } from "../format";
import type { UnitSystem } from "../format";

interface ActivitySelectorProps {
  selectedId: number | null;
  onSelect: (activity: Activity | null) => void;
  excludeIds?: number[];
  placeholder?: string;
  unitSystem?: UnitSystem;
  label?: string;
  className?: string;
}

export function ActivitySelector({
  selectedId,
  onSelect,
  excludeIds = [],
  placeholder = "Select an activity...",
  unitSystem = "metric",
  label,
  className = "",
}: ActivitySelectorProps) {
  // Use shared cached activities hook
  const { activities, loading, error } = useActivities();
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter activities based on search and exclusions
  const filteredActivities = useMemo(() => {
    return activities
      .filter((a) => !excludeIds.includes(a.id))
      .filter((a) => {
        if (!search) return true;
        const searchLower = search.toLowerCase();
        const title = a.title || "Untitled";
        const date = new Date(a.started_at).toLocaleDateString();
        return (
          title.toLowerCase().includes(searchLower) ||
          date.includes(searchLower)
        );
      });
  }, [activities, excludeIds, search]);

  // Get selected activity
  const selectedActivity = useMemo(() => {
    return activities.find((a) => a.id === selectedId) ?? null;
  }, [activities, selectedId]);

  // Format activity display
  const formatActivityDisplay = (activity: Activity) => {
    const title = activity.title || "Untitled";
    const date = new Date(activity.started_at).toLocaleDateString();
    const distance = formatDistance(activity.total_distance_m, unitSystem);
    const duration = formatTime(activity.moving_time_s);
    return { title, date, distance, duration };
  };

  const handleSelect = (activity: Activity) => {
    onSelect(activity);
    setIsOpen(false);
    setSearch("");
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(null);
    setSearch("");
  };

  const handleInputClick = () => {
    setIsOpen(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsOpen(false);
      setSearch("");
    }
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {label}
        </label>
      )}
      
      {/* Selected display / Input trigger */}
      <div
        onClick={handleInputClick}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white cursor-pointer hover:border-indigo-400 dark:hover:border-indigo-500 transition-colors flex items-center justify-between min-h-[42px]"
      >
        {isOpen ? (
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 bg-transparent border-none outline-none text-sm"
            autoFocus
          />
        ) : selectedActivity ? (
          <div className="flex-1 flex items-center justify-between">
            <div className="truncate">
              <span className="font-medium">{selectedActivity.title || "Untitled"}</span>
              <span className="text-gray-500 dark:text-gray-400 text-sm ml-2">
                {new Date(selectedActivity.started_at).toLocaleDateString()}
              </span>
            </div>
            <button
              onClick={handleClear}
              className="ml-2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              aria-label="Clear selection"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ) : (
          <span className="text-gray-500 dark:text-gray-400 text-sm">{placeholder}</span>
        )}
        
        {/* Dropdown arrow */}
        {!isOpen && !selectedActivity && (
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg max-h-80 overflow-auto">
          {loading ? (
            <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
              Loading activities...
            </div>
          ) : error ? (
            <div className="px-4 py-3 text-sm text-red-500 dark:text-red-400">
              {error}
            </div>
          ) : filteredActivities.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
              {search ? "No activities match your search" : "No activities available"}
            </div>
          ) : (
            <ul className="py-1">
              {filteredActivities.map((activity) => {
                const { title, date, distance, duration } = formatActivityDisplay(activity);
                const isSelected = activity.id === selectedId;
                
                return (
                  <li key={activity.id}>
                    <button
                      onClick={() => handleSelect(activity)}
                      className={`w-full px-4 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                        isSelected ? "bg-indigo-50 dark:bg-indigo-900/30" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="truncate">
                          <span className={`font-medium ${isSelected ? "text-indigo-600 dark:text-indigo-400" : "text-gray-900 dark:text-white"}`}>
                            {title}
                          </span>
                          {activity.is_breakthrough && (
                            <span className="ml-2 text-amber-500" title="Breakthrough ride">
                              <svg className="w-3 h-3 inline" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                              </svg>
                            </span>
                          )}
                        </div>
                        {isSelected && (
                          <svg className="w-4 h-4 text-indigo-600 dark:text-indigo-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {date} · {distance} · {duration}
                        {activity.tss && (
                          <span className="ml-1">· {activity.tss} TSS</span>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
