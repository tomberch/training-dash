import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import type { Activity } from "../api";
import { useActivities } from "../hooks/useActivities";
import { formatDistance, formatTime } from "../format";
import type { UnitSystem } from "../format";

/** Debounce delay for search input (ms) */
const SEARCH_DEBOUNCE_MS = 150;

interface ActivitySelectorProps {
  selectedId: number | null;
  onSelect: (activity: Activity | null) => void;
  excludeIds?: number[];
  placeholder?: string;
  unitSystem?: UnitSystem;
  label?: string;
  className?: string;
}

/** Loading skeleton for activity list items */
function ActivitySkeleton() {
  return (
    <div className="px-4 py-2 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2" />
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
        </div>
      </div>
    </div>
  );
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
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setHighlightedIndex(-1);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter activities based on debounced search and exclusions
  const filteredActivities = useMemo(() => {
    return activities
      .filter((a) => !excludeIds.includes(a.id))
      .filter((a) => {
        if (!debouncedSearch) return true;
        const searchLower = debouncedSearch.toLowerCase();
        const title = a.title || "Untitled";
        const date = new Date(a.started_at).toLocaleDateString();
        return (
          title.toLowerCase().includes(searchLower) ||
          date.includes(searchLower)
        );
      });
  }, [activities, excludeIds, debouncedSearch]);

  // Reset highlighted index when filtered activities change
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [filteredActivities.length]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const item = listRef.current.children[highlightedIndex] as HTMLElement;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex]);

  // Get selected activity
  const selectedActivity = useMemo(() => {
    return activities.find((a) => a.id === selectedId) ?? null;
  }, [activities, selectedId]);

  // Format activity display
  const formatActivityDisplay = useCallback((activity: Activity) => {
    const title = activity.title || "Untitled";
    const date = new Date(activity.started_at).toLocaleDateString();
    const distance = formatDistance(activity.total_distance_m, unitSystem);
    const duration = formatTime(activity.moving_time_s);
    return { title, date, distance, duration };
  }, [unitSystem]);

  const handleSelect = useCallback((activity: Activity) => {
    onSelect(activity);
    setIsOpen(false);
    setSearch("");
    setDebouncedSearch("");
    setHighlightedIndex(-1);
  }, [onSelect]);

  const handleClear = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(null);
    setSearch("");
    setDebouncedSearch("");
  }, [onSelect]);

  const handleInputClick = useCallback(() => {
    setIsOpen(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!isOpen) {
      // Open dropdown on arrow down or enter when closed
      if (e.key === "ArrowDown" || e.key === "Enter") {
        e.preventDefault();
        setIsOpen(true);
        return;
      }
      return;
    }

    switch (e.key) {
      case "Escape":
        e.preventDefault();
        setIsOpen(false);
        setSearch("");
        setDebouncedSearch("");
        setHighlightedIndex(-1);
        break;

      case "ArrowDown":
        e.preventDefault();
        setHighlightedIndex((prev) => 
          prev < filteredActivities.length - 1 ? prev + 1 : prev
        );
        break;

      case "ArrowUp":
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : 0));
        break;

      case "Enter":
        e.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < filteredActivities.length) {
          handleSelect(filteredActivities[highlightedIndex]);
        }
        break;

      case "Tab":
        // Allow tab to close dropdown naturally
        setIsOpen(false);
        setHighlightedIndex(-1);
        break;
    }
  }, [isOpen, filteredActivities, highlightedIndex, handleSelect]);

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
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-controls="activity-listbox"
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white cursor-pointer hover:border-indigo-400 dark:hover:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors flex items-center justify-between min-h-[42px]"
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
            aria-autocomplete="list"
            aria-controls="activity-listbox"
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
              type="button"
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
        <div 
          className="absolute z-50 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg max-h-80 overflow-auto"
          role="listbox"
          id="activity-listbox"
        >
          {loading ? (
            // Loading skeletons
            <div className="py-1">
              <ActivitySkeleton />
              <ActivitySkeleton />
              <ActivitySkeleton />
            </div>
          ) : error ? (
            <div className="px-4 py-3 text-sm text-red-500 dark:text-red-400">
              {error}
            </div>
          ) : filteredActivities.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
              {debouncedSearch ? "No activities match your search" : "No activities available"}
            </div>
          ) : (
            <ul ref={listRef} className="py-1">
              {filteredActivities.map((activity, index) => {
                const { title, date, distance, duration } = formatActivityDisplay(activity);
                const isSelected = activity.id === selectedId;
                const isHighlighted = index === highlightedIndex;
                
                return (
                  <li 
                    key={activity.id}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <button
                      onClick={() => handleSelect(activity)}
                      onMouseEnter={() => setHighlightedIndex(index)}
                      type="button"
                      className={`w-full px-4 py-2 text-left transition-colors ${
                        isHighlighted
                          ? "bg-indigo-50 dark:bg-indigo-900/40"
                          : isSelected
                          ? "bg-indigo-50/50 dark:bg-indigo-900/20"
                          : "hover:bg-gray-100 dark:hover:bg-gray-700"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="truncate">
                          <span className={`font-medium ${
                            isSelected || isHighlighted 
                              ? "text-indigo-600 dark:text-indigo-400" 
                              : "text-gray-900 dark:text-white"
                          }`}>
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
