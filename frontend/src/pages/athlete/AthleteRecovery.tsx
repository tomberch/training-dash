import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AthleteRecovery() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Recovery Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <p className="text-sm text-muted-foreground">
              Monitor your resting heart rate and HRV to track recovery status.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
