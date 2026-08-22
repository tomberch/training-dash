import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BikeTypeBadge } from "@/components/BikeTypeBadge";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
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

  // Check if we have estimated aero data
  const hasEstimatedAero = bike.estimated_cda_avg !== null || bike.estimated_crr_avg !== null;

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

        {/* Estimated Aero Section */}
        {hasEstimatedAero && (
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2 mb-3">
              <svg className="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide cursor-help">
                    Estimated from {bike.aero_sample_count ?? 0} rides
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p>Averaged from activities with measured power, GPS, and weather data. Higher sample count = more reliable.</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              {bike.estimated_cda_avg !== null && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="cursor-help">
                      <div className="text-muted-foreground flex items-center gap-1">
                        Est. CdA
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="font-medium">
                        {bike.estimated_cda_avg.toFixed(3)}
                        {bike.estimated_cda_stddev !== null && (
                          <span className="text-muted-foreground text-xs ml-1">
                            ±{bike.estimated_cda_stddev.toFixed(3)}
                          </span>
                        )}
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="font-medium">Estimated Drag Area</p>
                    <p className="text-xs mt-1">Confidence-weighted average from your rides. Typical road: 0.25-0.35, TT: 0.20-0.25</p>
                  </TooltipContent>
                </Tooltip>
              )}
              {bike.estimated_crr_avg !== null && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="cursor-help">
                      <div className="text-muted-foreground flex items-center gap-1">
                        Est. Crr
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="font-medium">
                        {bike.estimated_crr_avg.toFixed(4)}
                        {bike.estimated_crr_stddev !== null && (
                          <span className="text-muted-foreground text-xs ml-1">
                            ±{bike.estimated_crr_stddev.toFixed(4)}
                          </span>
                        )}
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="font-medium">Estimated Rolling Resistance</p>
                    <p className="text-xs mt-1">Confidence-weighted average. Typical smooth road: 0.003-0.005, gravel: 0.006-0.010</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
