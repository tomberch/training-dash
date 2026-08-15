import type { JSX } from "react";
import { useState, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  FIELD_DEFINITIONS,
  type FieldType,
  type FieldDef,
} from "@/lib/query/fields";

// === Types ===

export interface Condition {
  id: string;
  field: string;
  operator: string;
  value: string;
  conjunction: "AND" | "OR";
}

export interface QueryBuilderProps {
  onQueryChange: (query: string) => void;
  initialQuery?: string;
}

// === Icons ===

function PlusIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

// === Field Metadata ===

// Group fields by category for better UX
const FIELD_GROUPS: Record<string, string[]> = {
  "Time & Date": ["started_at"],
  "Distance & Speed": ["total_distance_m", "avg_speed_mps", "max_speed_mps"],
  "Duration": ["moving_time_s", "elapsed_time_s"],
  "Heart Rate": ["avg_hr_bpm", "max_hr_bpm"],
  "Power": ["avg_power_w", "np_power_w", "power_source", "power_confidence"],
  "Training Load": ["tss", "intensity_factor", "training_load", "wbal_min_joules", "wbal_min_pct"],
  "Elevation": ["elevation_gain_m"],
  "Activity Info": ["title", "source", "is_breakthrough", "route_id", "direction_bearing", "id"],
};

function formatFieldLabel(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/Bpm$/, " (bpm)")
    .replace(/ M$/, " (m)")
    .replace(/ S$/, " (s)")
    .replace(/Mps$/, " (m/s)")
    .replace(/ W$/, " (W)");
}

// Operators by field type with display labels
const OPERATOR_OPTIONS: Record<FieldType, Array<{ value: string; label: string }>> = {
  number: [
    { value: "=", label: "equals" },
    { value: "!=", label: "not equals" },
    { value: ">", label: "greater than" },
    { value: ">=", label: "at least" },
    { value: "<", label: "less than" },
    { value: "<=", label: "at most" },
  ],
  string: [
    { value: "=", label: "equals" },
    { value: "!=", label: "not equals" },
    { value: "CONTAINS", label: "contains" },
    { value: "STARTS_WITH", label: "starts with" },
    { value: "ENDS_WITH", label: "ends with" },
  ],
  date: [
    { value: "=", label: "on" },
    { value: "!=", label: "not on" },
    { value: ">", label: "after" },
    { value: ">=", label: "on or after" },
    { value: "<", label: "before" },
    { value: "<=", label: "on or before" },
  ],
  boolean: [
    { value: "=", label: "is" },
  ],
  duration: [
    { value: "=", label: "equals" },
    { value: "!=", label: "not equals" },
    { value: ">", label: "more than" },
    { value: ">=", label: "at least" },
    { value: "<", label: "less than" },
    { value: "<=", label: "at most" },
  ],
};

// Date presets for quick selection
const DATE_PRESETS = [
  { value: "TODAY", label: "Today" },
  { value: "START_OF_WEEK", label: "This week" },
  { value: "START_OF_MONTH", label: "This month" },
  { value: "START_OF_YEAR", label: "This year" },
  { value: "TODAY - 7", label: "Last 7 days" },
  { value: "TODAY - 30", label: "Last 30 days" },
  { value: "TODAY - 90", label: "Last 90 days" },
];

// === Helper Functions ===

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

function getDefaultOperator(fieldType: FieldType): string {
  switch (fieldType) {
    case "date":
      return ">=";
    case "boolean":
      return "=";
    case "string":
      return "=";
    default:
      return ">";
  }
}

function getDefaultValue(fieldType: FieldType): string {
  switch (fieldType) {
    case "date":
      return "START_OF_MONTH";
    case "boolean":
      return "true";
    case "number":
    case "duration":
      return "";
    default:
      return "";
  }
}

function formatValueForQuery(value: string, fieldDef: FieldDef): string {
  if (fieldDef.fieldType === "string") {
    // Escape backslashes first, then quotes (order matters!)
    const escaped = value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    return `"${escaped}"`;
  }
  if (fieldDef.fieldType === "boolean") {
    return value.toLowerCase() === "true" ? "true" : "false";
  }
  // Numbers, dates, and durations are used as-is
  return value;
}

function conditionsToQuery(conditions: Condition[]): string {
  if (conditions.length === 0) return "";

  const parts: string[] = [];

  for (let i = 0; i < conditions.length; i++) {
    const cond = conditions[i];
    if (!cond.field || !cond.value) continue;

    const fieldDef = FIELD_DEFINITIONS[cond.field];
    if (!fieldDef) continue;

    const formattedValue = formatValueForQuery(cond.value, fieldDef);
    let clause: string;

    // Handle text match operators
    if (["CONTAINS", "STARTS_WITH", "ENDS_WITH"].includes(cond.operator)) {
      clause = `${cond.field} ${cond.operator} ${formattedValue}`;
    } else {
      clause = `${cond.field} ${cond.operator} ${formattedValue}`;
    }

    if (i === 0) {
      parts.push(clause);
    } else {
      parts.push(`${cond.conjunction} ${clause}`);
    }
  }

  return parts.join(" ");
}

// === Condition Row Component ===

interface ConditionRowProps {
  condition: Condition;
  isFirst: boolean;
  onChange: (id: string, updates: Partial<Condition>) => void;
  onRemove: (id: string) => void;
}

function ConditionRow({ condition, isFirst, onChange, onRemove }: ConditionRowProps) {
  const fieldDef = FIELD_DEFINITIONS[condition.field];
  const fieldType = fieldDef?.fieldType || "string";
  const operators = OPERATOR_OPTIONS[fieldType] || OPERATOR_OPTIONS.string;

  const handleFieldChange = (newField: string) => {
    const newFieldDef = FIELD_DEFINITIONS[newField];
    const newFieldType = newFieldDef?.fieldType || "string";
    const currentFieldType = fieldDef?.fieldType;
    
    // Reset operator when field type changes OR when selecting first field
    const shouldResetOperator = !currentFieldType || newFieldType !== currentFieldType;

    onChange(condition.id, {
      field: newField,
      operator: shouldResetOperator ? getDefaultOperator(newFieldType) : condition.operator,
      value: shouldResetOperator ? getDefaultValue(newFieldType) : condition.value,
    });
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Conjunction (AND/OR) - only show for non-first conditions */}
      {!isFirst && (
        <select
          value={condition.conjunction}
          onChange={(e) => onChange(condition.id, { conjunction: e.target.value as "AND" | "OR" })}
          className="px-2 py-1.5 text-sm rounded border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          <option value="AND">AND</option>
          <option value="OR">OR</option>
        </select>
      )}

      {/* Field selector */}
      <select
        value={condition.field}
        onChange={(e) => handleFieldChange(e.target.value)}
        className="flex-1 min-w-[160px] px-3 py-1.5 text-sm rounded border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
      >
        <option value="">Select field...</option>
        {Object.entries(FIELD_GROUPS).map(([group, fields]) => (
          <optgroup key={group} label={group}>
            {fields.map((field) => {
              const def = FIELD_DEFINITIONS[field];
              if (!def) return null;
              return (
                <option key={field} value={field}>
                  {formatFieldLabel(field)}
                </option>
              );
            })}
          </optgroup>
        ))}
      </select>

      {/* Operator selector */}
      <select
        value={condition.operator}
        onChange={(e) => onChange(condition.id, { operator: e.target.value })}
        className="px-3 py-1.5 text-sm rounded border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        disabled={!condition.field}
      >
        {operators.map((op) => (
          <option key={op.value} value={op.value}>
            {op.label}
          </option>
        ))}
      </select>

      {/* Value input - varies by field type */}
      {fieldType === "date" ? (
        <select
          value={condition.value}
          onChange={(e) => onChange(condition.id, { value: e.target.value })}
          className="flex-1 min-w-[140px] px-3 py-1.5 text-sm rounded border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          <option value="">Select date...</option>
          {DATE_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      ) : fieldType === "boolean" ? (
        <select
          value={condition.value}
          onChange={(e) => onChange(condition.id, { value: e.target.value })}
          className="px-3 py-1.5 text-sm rounded border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      ) : (
        <Input
          type={fieldType === "number" || fieldType === "duration" ? "text" : "text"}
          value={condition.value}
          onChange={(e) => onChange(condition.id, { value: e.target.value })}
          placeholder={getPlaceholder(fieldType, fieldDef)}
          className="flex-1 min-w-[120px] text-sm"
          disabled={!condition.field}
        />
      )}

      {/* Remove button */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onRemove(condition.id)}
        className="text-muted-foreground hover:text-destructive p-1.5"
        aria-label="Remove condition"
      >
        <TrashIcon />
      </Button>
    </div>
  );
}

function getPlaceholder(fieldType: FieldType, fieldDef: FieldDef | undefined): string {
  if (fieldType === "duration") {
    return "e.g., 1h30m or 5400";
  }
  if (fieldType === "number") {
    if (fieldDef?.internalUnit === "m") {
      return "e.g., 50km or 50000";
    }
    if (fieldDef?.internalUnit === "mps") {
      return "e.g., 30kph or 8.33";
    }
    return "Enter value...";
  }
  return "Enter value...";
}

// === Main Component ===

export function QueryBuilder({ onQueryChange, initialQuery: _initialQuery }: QueryBuilderProps): JSX.Element {
  const [conditions, setConditions] = useState<Condition[]>(() => {
    // Start with one empty condition
    return [
      {
        id: generateId(),
        field: "",
        operator: ">",
        value: "",
        conjunction: "AND",
      },
    ];
  });

  // Generate query string when conditions change
  const queryString = useMemo(() => conditionsToQuery(conditions), [conditions]);

  // Notify parent of query changes
  const handleConditionsChange = useCallback(
    (newConditions: Condition[]) => {
      setConditions(newConditions);
      const query = conditionsToQuery(newConditions);
      onQueryChange(query);
    },
    [onQueryChange]
  );

  const handleAddCondition = () => {
    const newCondition: Condition = {
      id: generateId(),
      field: "",
      operator: ">",
      value: "",
      conjunction: "AND",
    };
    handleConditionsChange([...conditions, newCondition]);
  };

  const handleUpdateCondition = (id: string, updates: Partial<Condition>) => {
    const newConditions = conditions.map((c) =>
      c.id === id ? { ...c, ...updates } : c
    );
    handleConditionsChange(newConditions);
  };

  const handleRemoveCondition = (id: string) => {
    // Don't remove the last condition
    if (conditions.length <= 1) {
      // Reset the condition instead
      handleConditionsChange([
        {
          id: generateId(),
          field: "",
          operator: ">",
          value: "",
          conjunction: "AND",
        },
      ]);
      return;
    }
    const newConditions = conditions.filter((c) => c.id !== id);
    handleConditionsChange(newConditions);
  };

  const handleClear = () => {
    handleConditionsChange([
      {
        id: generateId(),
        field: "",
        operator: ">",
        value: "",
        conjunction: "AND",
      },
    ]);
  };

  // Check if query is valid (has at least one complete condition)
  const isValid = conditions.some((c) => c.field && c.value);

  return (
    <div className="space-y-4">
      {/* Condition rows */}
      <div className="space-y-2">
        {conditions.map((condition, index) => (
          <ConditionRow
            key={condition.id}
            condition={condition}
            isFirst={index === 0}
            onChange={handleUpdateCondition}
            onRemove={handleRemoveCondition}
          />
        ))}
      </div>

      {/* Actions row */}
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAddCondition}
          className="gap-1"
        >
          <PlusIcon />
          Add Condition
        </Button>
        {conditions.length > 0 && isValid && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="text-muted-foreground"
          >
            Clear All
          </Button>
        )}
      </div>

      {/* Preview */}
      {queryString && (
        <div className="p-3 bg-muted/50 rounded-lg">
          <div className="text-caption mb-1">Generated query:</div>
          <code className="text-sm font-mono text-foreground">{queryString}</code>
        </div>
      )}
    </div>
  );
}
