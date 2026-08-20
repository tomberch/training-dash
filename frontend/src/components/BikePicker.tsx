import { useState, useEffect } from "react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { BikeTypeBadge } from "@/components/BikeTypeBadge";
import { fetchBikes } from "@/api/bikes";
import type { Bike, BikeSummary } from "@/api/types";
import { cn } from "@/lib/utils";

interface BikePickerProps {
  /** Currently selected bike (from activity) */
  selectedBike: BikeSummary | null;
  /** The user's default bike (for "assumed default" indicator) */
  defaultBike?: Bike | null;
  /** Called when user selects a different bike */
  onChange: (bikeId: number | null) => Promise<void>;
  /** Whether the picker is disabled (e.g., while saving) */
  disabled?: boolean;
  className?: string;
}

export function BikePicker({
  selectedBike,
  defaultBike,
  onChange,
  disabled = false,
  className,
}: BikePickerProps) {
  const [bikes, setBikes] = useState<Bike[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Fetch active bikes on mount
  useEffect(() => {
    async function loadBikes() {
      try {
        const data = await fetchBikes(false); // Only active bikes
        setBikes(data);
      } catch {
        // Silently fail - picker will just show current selection
      } finally {
        setLoading(false);
      }
    }
    loadBikes();
  }, []);

  async function handleSelect(bikeId: number | null) {
    if (bikeId === selectedBike?.id) return;
    setSaving(true);
    try {
      await onChange(bikeId);
    } finally {
      setSaving(false);
    }
  }

  const isDisabled = disabled || saving || loading;

  // Show "assumed default" if no bike selected but default exists
  const showAssumedDefault = !selectedBike && defaultBike;

  // Check if selected bike is retired (not in active bikes list)
  const selectedIsRetired =
    selectedBike && !bikes.some((b) => b.id === selectedBike.id);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          disabled={isDisabled}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 text-sm rounded-md hover:bg-muted transition disabled:opacity-50",
            className
          )}
        >
          {saving ? (
            <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          ) : (
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          )}

          {selectedBike ? (
            <span className={cn(selectedIsRetired && "text-muted-foreground line-through")}>
              {selectedBike.name}
            </span>
          ) : showAssumedDefault ? (
            <span className="text-muted-foreground italic">
              {defaultBike.name} (assumed)
            </span>
          ) : (
            <span className="text-muted-foreground">No bike</span>
          )}

          <svg
            className="w-3.5 h-3.5 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="min-w-[200px]">
        {/* None option */}
        <DropdownMenuItem
          onClick={() => handleSelect(null)}
          className={cn(!selectedBike && "bg-muted")}
        >
          <span className="text-muted-foreground">None</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Loading state */}
        {loading && (
          <DropdownMenuItem disabled>
            <span className="text-muted-foreground">Loading bikes...</span>
          </DropdownMenuItem>
        )}

        {/* No bikes available */}
        {!loading && bikes.length === 0 && (
          <DropdownMenuItem disabled>
            <span className="text-muted-foreground">No bikes configured</span>
          </DropdownMenuItem>
        )}

        {/* Active bikes */}
        {!loading &&
          bikes.map((bike) => (
            <DropdownMenuItem
              key={bike.id}
              onClick={() => handleSelect(bike.id)}
              className={cn(
                "flex items-center justify-between gap-2",
                selectedBike?.id === bike.id && "bg-muted"
              )}
            >
              <span className="flex items-center gap-2">
                {bike.name}
                {bike.is_default && (
                  <span className="text-warning" title="Default bike">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  </span>
                )}
              </span>
              <BikeTypeBadge type={bike.bike_type} />
            </DropdownMenuItem>
          ))}

        {/* Show retired bike if currently selected */}
        {selectedIsRetired && selectedBike && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled className="flex items-center justify-between gap-2 opacity-60">
              <span className="line-through">{selectedBike.name} (retired)</span>
              <BikeTypeBadge type={selectedBike.bike_type} />
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
