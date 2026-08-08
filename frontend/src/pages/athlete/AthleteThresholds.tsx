import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AthleteThresholds() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Thresholds</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <p className="text-sm text-muted-foreground">
              Manage your FTP, LTHR, and HRmax values over time.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
