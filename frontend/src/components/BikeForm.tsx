import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { Bike, BikeType, BikeCreateRequest, BikeUpdateRequest } from "@/api/types";
import { BIKE_TYPES, BIKE_TYPE_LABELS } from "@/api/types";

interface BikeFormProps {
  open: boolean;
  onClose: () => void;
  bike?: Bike;
  onSave: (data: BikeCreateRequest | BikeUpdateRequest) => Promise<void>;
}

export function BikeForm({ open, onClose, bike, onSave }: BikeFormProps) {
  const isEditMode = !!bike;

  // Form state
  const [name, setName] = useState("");
  const [bikeType, setBikeType] = useState<BikeType>("road");
  const [modelYear, setModelYear] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [cda, setCda] = useState("");
  const [crr, setCrr] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens or bike changes
  useEffect(() => {
    if (open) {
      if (bike) {
        setName(bike.name);
        setBikeType(bike.bike_type);
        setModelYear(bike.model_year?.toString() || "");
        setWeightKg(bike.weight_kg?.toString() || "");
        setCda(bike.cda?.toString() || "");
        setCrr(bike.crr?.toString() || "");
        setIsDefault(bike.is_default);
      } else {
        setName("");
        setBikeType("road");
        setModelYear("");
        setWeightKg("");
        setCda("");
        setCrr("");
        setIsDefault(false);
      }
      setError(null);
    }
  }, [open, bike]);

  // Validation
  function validate(): string | null {
    if (!name.trim()) return "Name is required";
    if (!bikeType) return "Bike type is required";

    if (modelYear && (isNaN(parseInt(modelYear)) || parseInt(modelYear) < 1900 || parseInt(modelYear) > new Date().getFullYear() + 1)) {
      return "Invalid model year";
    }
    if (weightKg && (isNaN(parseFloat(weightKg)) || parseFloat(weightKg) <= 0 || parseFloat(weightKg) > 50)) {
      return "Weight must be between 0 and 50 kg";
    }
    if (cda && (isNaN(parseFloat(cda)) || parseFloat(cda) <= 0 || parseFloat(cda) > 1)) {
      return "CdA must be between 0 and 1";
    }
    if (crr && (isNaN(parseFloat(crr)) || parseFloat(crr) <= 0 || parseFloat(crr) > 0.1)) {
      return "Crr must be between 0 and 0.1";
    }

    return null;
  }

  async function handleSave() {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (isEditMode) {
        const updateData: BikeUpdateRequest = {
          name: name.trim(),
          bike_type: bikeType,
          model_year: modelYear ? parseInt(modelYear) : null,
          weight_kg: weightKg ? parseFloat(weightKg) : null,
          cda: cda ? parseFloat(cda) : null,
          crr: crr ? parseFloat(crr) : null,
        };
        await onSave(updateData);
      } else {
        const createData: BikeCreateRequest = {
          name: name.trim(),
          bike_type: bikeType,
          model_year: modelYear ? parseInt(modelYear) : null,
          weight_kg: weightKg ? parseFloat(weightKg) : null,
          cda: cda ? parseFloat(cda) : null,
          crr: crr ? parseFloat(crr) : null,
          is_default: isDefault,
        };
        await onSave(createData);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  const title = isEditMode ? "Edit Bike" : "Add Bike";

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
          className="space-y-4"
        >
          {/* Name field */}
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Canyon Aeroad"
              autoFocus
            />
          </div>

          {/* Bike type field */}
          <div className="space-y-1.5">
            <Label htmlFor="bike_type">Type</Label>
            <select
              id="bike_type"
              value={bikeType}
              onChange={(e) => setBikeType(e.target.value as BikeType)}
              className={cn(
                "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              )}
            >
              {BIKE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {BIKE_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          {/* Model year field */}
          <div className="space-y-1.5">
            <Label htmlFor="model_year">Model Year (optional)</Label>
            <Input
              id="model_year"
              type="number"
              value={modelYear}
              onChange={(e) => setModelYear(e.target.value)}
              placeholder="e.g., 2024"
              min={1900}
              max={new Date().getFullYear() + 1}
            />
          </div>

          {/* Weight field */}
          <div className="space-y-1.5">
            <Label htmlFor="weight_kg">Weight (kg, optional)</Label>
            <Input
              id="weight_kg"
              type="number"
              step="0.1"
              value={weightKg}
              onChange={(e) => setWeightKg(e.target.value)}
              placeholder="e.g., 7.5"
              min={0}
              max={50}
            />
          </div>

          {/* CdA field */}
          <div className="space-y-1.5">
            <Label htmlFor="cda">CdA (optional)</Label>
            <Input
              id="cda"
              type="number"
              step="0.001"
              value={cda}
              onChange={(e) => setCda(e.target.value)}
              placeholder="e.g., 0.250"
              min={0}
              max={1}
            />
            <p className="text-caption">Coefficient of drag area (m²). Typical values: 0.20-0.35</p>
          </div>

          {/* Crr field */}
          <div className="space-y-1.5">
            <Label htmlFor="crr">Crr (optional)</Label>
            <Input
              id="crr"
              type="number"
              step="0.0001"
              value={crr}
              onChange={(e) => setCrr(e.target.value)}
              placeholder="e.g., 0.0035"
              min={0}
              max={0.1}
            />
            <p className="text-caption">Coefficient of rolling resistance. Typical values: 0.002-0.006</p>
          </div>

          {/* Is default field (only for create) */}
          {!isEditMode && (
            <div className="flex items-center gap-2">
              <input
                id="is_default"
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="is_default" className="font-normal">
                Set as default bike
              </Label>
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
              {error}
            </div>
          )}
        </form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
