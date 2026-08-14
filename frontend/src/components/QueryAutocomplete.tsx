import type { JSX } from "react";
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { cn } from "@/lib/utils";
import {
  FIELD_DEFINITIONS,
  FIELD_ALIASES,
  ALL_FIELD_NAMES,
  type FieldDef,
} from "@/lib/query/fields";

// === Types ===

interface Suggestion {
  value: string;
  label: string;
  description: string;
  type: "field" | "operator" | "keyword" | "value";
}

export interface QueryAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onExecute: () => void;
  placeholder?: string;
  disabled?: boolean;
  hasError?: boolean;
}

// === Constants ===

const OPERATORS = ["=", "!=", ">", ">=", "<", "<=", "AND", "OR", "NOT", "BETWEEN", "IN", "IS NULL", "IS NOT NULL", "CONTAINS", "STARTS WITH", "ENDS WITH"];

const KEYWORDS = ["WHERE", "ORDER BY", "ASC", "DESC", "LIMIT", "GROUP BY", "COUNT", "SUM", "AVG", "MIN", "MAX"];

const DATE_VALUES = ["TODAY", "NOW", "START_OF_DAY", "START_OF_WEEK", "START_OF_MONTH", "START_OF_YEAR"];

// Build field suggestions from definitions
const FIELD_SUGGESTIONS: Suggestion[] = Object.entries(FIELD_DEFINITIONS).map(
  ([name, def]) => ({
    value: name,
    label: formatFieldName(name),
    description: def.description,
    type: "field" as const,
  })
);

// Add commonly used aliases as suggestions
const ALIAS_SUGGESTIONS: Suggestion[] = [
  { value: "distance", label: "distance", description: "Alias for total_distance_m", type: "field" },
  { value: "duration", label: "duration", description: "Alias for moving_time_s", type: "field" },
  { value: "date", label: "date", description: "Alias for started_at", type: "field" },
  { value: "power", label: "power", description: "Alias for avg_power_w", type: "field" },
  { value: "hr", label: "hr", description: "Alias for avg_hr_bpm", type: "field" },
  { value: "speed", label: "speed", description: "Alias for avg_speed_mps", type: "field" },
];

const DATE_SUGGESTIONS: Suggestion[] = DATE_VALUES.map((v) => ({
  value: v,
  label: v,
  description: getDateValueDescription(v),
  type: "value" as const,
}));

function formatFieldName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getDateValueDescription(value: string): string {
  switch (value) {
    case "TODAY":
      return "Start of today (midnight)";
    case "NOW":
      return "Current date and time";
    case "START_OF_DAY":
      return "Start of today";
    case "START_OF_WEEK":
      return "Start of current week (Monday)";
    case "START_OF_MONTH":
      return "Start of current month";
    case "START_OF_YEAR":
      return "Start of current year";
    default:
      return "";
  }
}

// === Helper Functions ===

function getWordAtCursor(text: string, cursorPos: number): { word: string; start: number; end: number } {
  // Find word boundaries around cursor
  let start = cursorPos;
  let end = cursorPos;

  // Move backwards to find word start
  while (start > 0 && /[a-zA-Z0-9_]/.test(text[start - 1])) {
    start--;
  }

  // Move forwards to find word end
  while (end < text.length && /[a-zA-Z0-9_]/.test(text[end])) {
    end++;
  }

  return {
    word: text.slice(start, end),
    start,
    end,
  };
}

function getSuggestions(text: string, cursorPos: number): Suggestion[] {
  const { word, start } = getWordAtCursor(text, cursorPos);
  
  if (!word) return [];

  const wordLower = word.toLowerCase();
  const textBeforeCursor = text.slice(0, start).trim().toLowerCase();
  
  // Determine context: are we after an operator?
  const lastToken = textBeforeCursor.split(/\s+/).pop() || "";
  const isAfterDateField = /(?:date|started_at|start)\s*(?:=|!=|>|>=|<|<=)\s*$/i.test(textBeforeCursor);
  const isAfterOperator = /(?:=|!=|>|>=|<|<=)\s*$/i.test(textBeforeCursor);

  let candidates: Suggestion[] = [];

  // If after a date field comparison, suggest date values
  if (isAfterDateField || (isAfterOperator && wordLower.startsWith("s") || wordLower.startsWith("t") || wordLower.startsWith("n"))) {
    candidates = [...candidates, ...DATE_SUGGESTIONS];
  }

  // Always include fields as candidates
  candidates = [...candidates, ...FIELD_SUGGESTIONS, ...ALIAS_SUGGESTIONS];

  // Filter by prefix match
  const filtered = candidates.filter((s) =>
    s.value.toLowerCase().startsWith(wordLower) ||
    s.label.toLowerCase().startsWith(wordLower)
  );

  // Sort by relevance: exact prefix first, then alphabetically
  filtered.sort((a, b) => {
    const aExact = a.value.toLowerCase() === wordLower;
    const bExact = b.value.toLowerCase() === wordLower;
    if (aExact && !bExact) return -1;
    if (!aExact && bExact) return 1;
    return a.value.localeCompare(b.value);
  });

  // Limit results
  return filtered.slice(0, 10);
}

// === Component ===

export function QueryAutocomplete({
  value,
  onChange,
  onExecute,
  placeholder = "Enter query...",
  disabled = false,
  hasError = false,
}: QueryAutocompleteProps): JSX.Element {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.max(80, textarea.scrollHeight)}px`;
    }
  }, [value]);

  // Update suggestions when text or cursor changes
  const updateSuggestions = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const cursorPos = textarea.selectionStart;
    const newSuggestions = getSuggestions(value, cursorPos);
    
    setSuggestions(newSuggestions);
    setSelectedIndex(0);
    setShowSuggestions(newSuggestions.length > 0);
  }, [value]);

  // Handle input change
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
  };

  // Trigger suggestions on input
  useEffect(() => {
    const timeout = setTimeout(updateSuggestions, 50);
    return () => clearTimeout(timeout);
  }, [value, updateSuggestions]);

  // Apply suggestion
  const applySuggestion = useCallback((suggestion: Suggestion) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const cursorPos = textarea.selectionStart;
    const { start, end } = getWordAtCursor(value, cursorPos);

    const newValue = value.slice(0, start) + suggestion.value + value.slice(end);
    const newCursorPos = start + suggestion.value.length;

    onChange(newValue);
    setShowSuggestions(false);

    // Restore cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  }, [value, onChange]);

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showSuggestions && suggestions.length > 0) {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, suggestions.length - 1));
          return;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          return;
        case "Tab":
        case "Enter":
          if (e.key === "Enter" && !e.shiftKey && suggestions.length > 0) {
            e.preventDefault();
            applySuggestion(suggestions[selectedIndex]);
            return;
          }
          break;
        case "Escape":
          e.preventDefault();
          setShowSuggestions(false);
          return;
      }
    }

    // Ctrl/Cmd + Enter to execute
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (!disabled && value.trim()) {
        setShowSuggestions(false);
        onExecute();
      }
    }
  };

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(e.target as Node) &&
        !textareaRef.current?.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Scroll selected suggestion into view
  useEffect(() => {
    if (showSuggestions && suggestionsRef.current) {
      const selected = suggestionsRef.current.querySelector('[data-selected="true"]');
      // scrollIntoView may not be available in jsdom tests
      if (selected && typeof selected.scrollIntoView === "function") {
        selected.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex, showSuggestions]);

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onFocus={updateSuggestions}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          "w-full px-4 py-3 font-mono text-sm rounded-lg border resize-none",
          "bg-background text-foreground placeholder:text-muted-foreground",
          "focus:outline-none focus:ring-2 focus:ring-primary/50",
          hasError ? "border-destructive" : "border-border",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        rows={2}
      />

      {/* Suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute left-0 right-0 top-full mt-1 bg-card border border-border rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={suggestion.value}
              type="button"
              data-selected={index === selectedIndex}
              className={cn(
                "w-full text-left px-3 py-2 flex items-start gap-3 transition-colors",
                index === selectedIndex
                  ? "bg-primary/10 text-foreground"
                  : "hover:bg-muted/50 text-foreground"
              )}
              onClick={() => applySuggestion(suggestion)}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <span className="font-mono text-sm shrink-0">{suggestion.value}</span>
              <span className="text-xs text-muted-foreground truncate">
                {suggestion.description}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// === Help Panel Component ===

export function QueryHelpPanel(): JSX.Element {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 text-left flex items-center justify-between bg-muted/30 hover:bg-muted/50 transition-colors"
      >
        <span className="text-sm font-medium text-foreground">Query Syntax Help</span>
        <svg
          className={cn("w-4 h-4 transition-transform", expanded && "rotate-180")}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="p-4 space-y-4 text-sm">
          {/* Basic Syntax */}
          <div>
            <h4 className="font-medium text-foreground mb-2">Basic Syntax</h4>
            <div className="space-y-1 text-muted-foreground">
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">field operator value</code> — Basic comparison</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">condition AND condition</code> — Combine conditions</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">condition OR condition</code> — Either condition</p>
            </div>
          </div>

          {/* Operators */}
          <div>
            <h4 className="font-medium text-foreground mb-2">Operators</h4>
            <div className="grid grid-cols-2 gap-1 text-muted-foreground">
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">=</code> <code className="text-xs bg-muted px-1 py-0.5 rounded">!=</code> — Equal / Not equal</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">&gt;</code> <code className="text-xs bg-muted px-1 py-0.5 rounded">&gt;=</code> <code className="text-xs bg-muted px-1 py-0.5 rounded">&lt;</code> <code className="text-xs bg-muted px-1 py-0.5 rounded">&lt;=</code> — Comparisons</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">BETWEEN x AND y</code> — Range</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">IN (a, b, c)</code> — List membership</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">IS NULL</code> — Check for null</p>
              <p><code className="text-xs bg-muted px-1 py-0.5 rounded">CONTAINS</code> — Text search</p>
            </div>
          </div>

          {/* Common Fields */}
          <div>
            <h4 className="font-medium text-foreground mb-2">Common Fields</h4>
            <div className="grid grid-cols-2 gap-1 text-muted-foreground text-xs">
              <p><code className="bg-muted px-1 py-0.5 rounded">tss</code> — Training Stress Score</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">distance</code> — Distance (accepts km, mi)</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">duration</code> — Moving time (accepts h, m, s)</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">date</code> — Activity date</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">power</code> — Average power (W)</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">hr</code> — Average heart rate (bpm)</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">elevation</code> — Elevation gain (m, ft)</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">title</code> — Activity name</p>
            </div>
          </div>

          {/* Date Values */}
          <div>
            <h4 className="font-medium text-foreground mb-2">Date Values</h4>
            <div className="grid grid-cols-2 gap-1 text-muted-foreground text-xs">
              <p><code className="bg-muted px-1 py-0.5 rounded">TODAY</code> — Start of today</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">START_OF_WEEK</code> — Monday</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">START_OF_MONTH</code> — 1st of month</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">START_OF_YEAR</code> — Jan 1st</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">TODAY - 7</code> — 7 days ago</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">2024-01-15</code> — Specific date</p>
            </div>
          </div>

          {/* Examples */}
          <div>
            <h4 className="font-medium text-foreground mb-2">Examples</h4>
            <div className="space-y-1 text-muted-foreground text-xs">
              <p><code className="bg-muted px-1 py-0.5 rounded">tss &gt; 100</code> — High-stress activities</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">distance &gt; 50km AND date &gt;= START_OF_MONTH</code> — Long rides this month</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">title CONTAINS "morning"</code> — Morning activities</p>
              <p><code className="bg-muted px-1 py-0.5 rounded">COUNT(*), AVG(tss) GROUP BY month</code> — Monthly stats</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
