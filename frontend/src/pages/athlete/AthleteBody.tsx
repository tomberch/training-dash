import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AthleteBody() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Body Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <p className="text-sm text-muted-foreground">
              Track your weight, height, and other body composition metrics.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
