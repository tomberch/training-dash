import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AthleteOverview() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-32 w-full" />
            <p className="text-sm text-muted-foreground">
              Summary of your current metrics across all categories will appear here.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
