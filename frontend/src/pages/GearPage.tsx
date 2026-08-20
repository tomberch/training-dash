import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { BikeCard } from "@/components/BikeCard";
import { BikeForm } from "@/components/BikeForm";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { fetchBikes, createBike, updateBike, setDefaultBike, retireBike } from "@/api/bikes";
import type { Bike, BikeCreateRequest, BikeUpdateRequest } from "@/api/types";
import type { UnitSystem } from "@/format";
import { cn } from "@/lib/utils";

interface GearPageProps {
  unitSystem: UnitSystem;
}

export function GearPage({ unitSystem }: GearPageProps) {
  const navigate = useNavigate();

  // Data state
  const [bikes, setBikes] = useState<Bike[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [showRetired, setShowRetired] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingBike, setEditingBike] = useState<Bike | undefined>(undefined);
  const [retireConfirmBike, setRetireConfirmBike] = useState<Bike | null>(null);

  // Fetch bikes
  const loadBikes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBikes(true); // Always fetch all, filter in UI
      setBikes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bikes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBikes();
  }, [loadBikes]);

  // Filter bikes
  const activeBikes = bikes.filter((b) => b.retired_at === null);
  const retiredBikes = bikes.filter((b) => b.retired_at !== null);

  // Handlers
  const handleOpenCreate = () => {
    setEditingBike(undefined);
    setFormOpen(true);
  };

  const handleOpenEdit = (bike: Bike) => {
    setEditingBike(bike);
    setFormOpen(true);
  };

  const handleSave = async (data: BikeCreateRequest | BikeUpdateRequest) => {
    if (editingBike) {
      await updateBike(editingBike.id, data as BikeUpdateRequest);
      toast.success("Bike updated");
    } else {
      await createBike(data as BikeCreateRequest);
      toast.success("Bike created");
    }
    await loadBikes();
  };

  const handleSetDefault = async (bike: Bike) => {
    try {
      await setDefaultBike(bike.id);
      toast.success(`${bike.name} set as default`);
      await loadBikes();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to set default");
    }
  };

  const handleRetireConfirm = async () => {
    if (!retireConfirmBike) return;
    try {
      await retireBike(retireConfirmBike.id);
      toast.success(`${retireConfirmBike.name} retired`);
      setRetireConfirmBike(null);
      await loadBikes();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to retire bike");
    }
  };

  return (
    <div className="p-8">
      <div className="flex items-center gap-4 mb-2">
        <button
          onClick={() => navigate("/settings")}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Back to settings"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <PageHeader
          title="Gear"
          subtitle="Manage your bikes and equipment"
        />
      </div>

      {/* Add bike button */}
      <div className="flex justify-end mb-6">
        <Button onClick={handleOpenCreate}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Bike
        </Button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 bg-muted rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive">
          {error}
          <Button variant="outline" size="sm" className="ml-4" onClick={loadBikes}>
            Retry
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && activeBikes.length === 0 && retiredBikes.length === 0 && (
        <div className="text-center py-12">
          <svg className="w-12 h-12 mx-auto text-muted-foreground mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <h3 className="text-lg font-medium mb-2">No bikes yet</h3>
          <p className="text-muted-foreground mb-4">Add your first bike to track distance and performance.</p>
          <Button onClick={handleOpenCreate}>Add Bike</Button>
        </div>
      )}

      {/* Active bikes */}
      {!loading && !error && activeBikes.length > 0 && (
        <div className="space-y-4">
          {activeBikes.map((bike) => (
            <BikeCard
              key={bike.id}
              bike={bike}
              unitSystem={unitSystem}
              onEdit={handleOpenEdit}
              onSetDefault={handleSetDefault}
              onRetire={(b) => setRetireConfirmBike(b)}
            />
          ))}
        </div>
      )}

      {/* Retired bikes section */}
      {!loading && !error && retiredBikes.length > 0 && (
        <div className="mt-8">
          <button
            onClick={() => setShowRetired(!showRetired)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <svg
              className={cn("w-4 h-4 transition-transform", showRetired && "rotate-90")}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Retired ({retiredBikes.length})
          </button>

          {showRetired && (
            <div className="mt-4 space-y-4">
              {retiredBikes.map((bike) => (
                <BikeCard
                  key={bike.id}
                  bike={bike}
                  unitSystem={unitSystem}
                  onEdit={handleOpenEdit}
                  onSetDefault={handleSetDefault}
                  onRetire={(b) => setRetireConfirmBike(b)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bike form modal */}
      <BikeForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        bike={editingBike}
        onSave={handleSave}
      />

      {/* Retire confirmation dialog */}
      <AlertDialog open={!!retireConfirmBike} onOpenChange={(open) => !open && setRetireConfirmBike(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retire {retireConfirmBike?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Retired bikes will no longer appear in the bike picker. You can still view them in the retired section.
              This action can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRetireConfirm}>Retire</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
