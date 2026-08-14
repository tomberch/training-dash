import type { JSX } from "react";
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { fetchSavedFilters, type SavedFilter } from "../api";

// === Icons ===

function FilterIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function StarIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg
      className={cn("w-3 h-3", filled ? "fill-current text-warning" : "")}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
      />
    </svg>
  );
}

// === Component ===

export interface SavedFiltersDropdownProps {
  className?: string;
}

export function SavedFiltersDropdown({ className }: SavedFiltersDropdownProps): JSX.Element {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<SavedFilter[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch filters when dropdown opens
  useEffect(() => {
    if (isOpen && filters.length === 0 && !loading) {
      setLoading(true);
      fetchSavedFilters()
        .then(setFilters)
        .catch(() => {
          // Silently fail - user just won't see filters
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, filters.length, loading]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen]);

  const handleFilterClick = (filter: SavedFilter) => {
    setIsOpen(false);
    // Navigate to query page with the filter's query
    navigate(`/query?q=${encodeURIComponent(filter.query)}`);
  };

  const handleNewQuery = () => {
    setIsOpen(false);
    navigate("/query");
  };

  // Sort filters: default first, then alphabetically
  const sortedFilters = [...filters].sort((a, b) => {
    if (a.is_default && !b.is_default) return -1;
    if (!a.is_default && b.is_default) return 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div ref={dropdownRef} className={cn("relative inline-block", className)}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-colors",
          "bg-card border-border text-foreground hover:bg-muted/50",
          isOpen && "bg-muted/50"
        )}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <FilterIcon />
        <span>Quick Filter</span>
        <ChevronDownIcon />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-64 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
          {loading ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              Loading filters...
            </div>
          ) : sortedFilters.length === 0 ? (
            <div className="p-4">
              <p className="text-sm text-muted-foreground mb-3">No saved filters yet.</p>
              <button
                type="button"
                onClick={handleNewQuery}
                className="w-full px-3 py-2 text-sm text-center text-primary hover:bg-muted/50 rounded-md transition-colors"
              >
                Create your first filter
              </button>
            </div>
          ) : (
            <>
              <div className="max-h-60 overflow-y-auto">
                {sortedFilters.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    onClick={() => handleFilterClick(filter)}
                    className="w-full px-3 py-2.5 text-left hover:bg-muted/50 transition-colors flex items-start gap-2"
                  >
                    {filter.is_default && (
                      <span className="shrink-0 mt-0.5">
                        <StarIcon filled />
                      </span>
                    )}
                    <div className={cn("flex-1 min-w-0", !filter.is_default && "pl-5")}>
                      <div className="text-sm font-medium text-foreground truncate">
                        {filter.name}
                      </div>
                      <div className="text-xs text-muted-foreground truncate font-mono">
                        {filter.query}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
              <div className="border-t border-border">
                <button
                  type="button"
                  onClick={handleNewQuery}
                  className="w-full px-3 py-2.5 text-sm text-center text-primary hover:bg-muted/50 transition-colors"
                >
                  Open Query Page
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
