import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AthleteFitness() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Fitness Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <p className="text-sm text-muted-foreground">
              Track your VO2max and other fitness indicators over time.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
