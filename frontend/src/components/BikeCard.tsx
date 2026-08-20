import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BikeTypeBadge } from "@/components/BikeTypeBadge";
import { formatDistance } from "@/format";
import type { Bike } from "@/api/types";
import type { UnitSystem } from "@/format";

interface BikeCardProps {
  bike: Bike;
  unitSystem: UnitSystem;
  onEdit: (bike: Bike) => void;
  onSetDefault: (bike: Bike) => void;
  onRetire: (bike: Bike) => void;
}

export function BikeCard({ bike, unitSystem, onEdit, onSetDefault, onRetire }: BikeCardProps) {
  const isRetired = bike.retired_at !== null;

  return (
    <Card className={isRetired ? "opacity-60" : undefined}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>{bike.name}</CardTitle>
          {bike.is_default && (
            <span className="text-warning" title="Default bike">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            </span>
          )}
        </div>
        <CardDescription>
          <BikeTypeBadge type={bike.bike_type} />
          {bike.model_year && <span className="ml-2 text-muted-foreground">{bike.model_year}</span>}
        </CardDescription>
        <CardAction>
          {!isRetired && (
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => onEdit(bike)}>
                Edit
              </Button>
              {!bike.is_default && (
                <Button variant="ghost" size="sm" onClick={() => onSetDefault(bike)}>
                  Set Default
                </Button>
              )}
              <Button variant="ghost" size="sm" className="text-destructive" onClick={() => onRetire(bike)}>
                Retire
              </Button>
            </div>
          )}
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground">Distance</div>
            <div className="font-medium">{formatDistance(bike.total_distance_m, unitSystem)}</div>
          </div>
          {bike.weight_kg !== null && (
            <div>
              <div className="text-muted-foreground">Weight</div>
              <div className="font-medium">{bike.weight_kg.toFixed(1)} kg</div>
            </div>
          )}
          {bike.cda !== null && (
            <div>
              <div className="text-muted-foreground">CdA</div>
              <div className="font-medium">
                {bike.cda.toFixed(3)}
                {bike.cda_source === "calibrated" && (
                  <span className="ml-1 text-xs text-success">(cal)</span>
                )}
              </div>
            </div>
          )}
          {bike.crr !== null && (
            <div>
              <div className="text-muted-foreground">Crr</div>
              <div className="font-medium">
                {bike.crr.toFixed(4)}
                {bike.crr_source === "calibrated" && (
                  <span className="ml-1 text-xs text-success">(cal)</span>
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
