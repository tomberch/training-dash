/**
 * Course List Page
 *
 * Table of user's courses with:
 * - Sortable columns
 * - Actions: View, Generate Plan, Delete
 */

import { useState, useEffect, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { fetchCourses, deleteCourse } from "@/api/race-plans";
import type { CourseListItem } from "@/api/types";

// =============================================================================
// Helper Functions
// =============================================================================

function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

function formatElevation(meters: number): string {
  return `${Math.round(meters)} m`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}


// =============================================================================
// Sort Types
// =============================================================================

type SortField = "name" | "distance" | "elevation" | "created";
type SortDirection = "asc" | "desc";

// =============================================================================
// Main Component
// =============================================================================

export function CourseList() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("created");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    setIsLoading(true);
    fetchCourses()
      .then(setCourses)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, []);

  const sortedCourses = useMemo(() => {
    const sorted = [...courses];
    sorted.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "distance":
          cmp = a.distance_m - b.distance_m;
          break;
        case "elevation":
          cmp = a.elevation_gain_m - b.elevation_gain_m;
          break;
        case "created":
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [courses, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handleDelete = async (courseId: number) => {
    setDeletingId(courseId);
    try {
      await deleteCourse(courseId);
      setCourses((prev) => prev.filter((c) => c.id !== courseId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  const SortIndicator = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return <span className="ml-1">{sortDirection === "asc" ? "↑" : "↓"}</span>;
  };


  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-32 mb-2" />
        <Skeleton className="h-4 w-48 mb-8" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-4">
          Failed to load courses: {error}
        </div>
        <Button variant="outline" onClick={() => navigate("/race-planner")}>
          Back to Race Planner
        </Button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
            <Link to="/race-planner" className="hover:text-foreground">
              Race Planner
            </Link>
            <span>/</span>
            <span>Courses</span>
          </div>
          <h1 className="text-page-title">Courses</h1>
          <p className="text-page-subtitle mt-1">
            {courses.length} course{courses.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Button onClick={() => navigate("/race-planner/courses/new")}>
          Upload Course
        </Button>
      </div>

      {courses.length === 0 ? (
        <div className="bg-card border border-border rounded-xl p-8 text-center">
          <p className="text-muted-foreground mb-4">No courses yet</p>
          <Button onClick={() => navigate("/race-planner/courses/new")}>
            Upload Your First Course
          </Button>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th
                    className="text-left py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("name")}
                  >
                    Name <SortIndicator field="name" />
                  </th>
                  <th
                    className="text-right py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("distance")}
                  >
                    Distance <SortIndicator field="distance" />
                  </th>
                  <th
                    className="text-right py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("elevation")}
                  >
                    Elevation <SortIndicator field="elevation" />
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">
                    Source
                  </th>
                  <th
                    className="text-left py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("created")}
                  >
                    Created <SortIndicator field="created" />
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedCourses.map((course) => (
                  <tr
                    key={course.id}
                    className="border-b border-border/50 hover:bg-muted/20 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <Link
                        to={`/race-planner/courses/${course.id}`}
                        className="font-medium hover:text-primary hover:underline"
                      >
                        {course.name}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums">
                      {formatDistance(course.distance_m)}
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums">
                      {formatElevation(course.elevation_gain_m)}
                    </td>
                    <td className="py-3 px-4 uppercase text-xs text-muted-foreground">
                      {course.source_type}
                    </td>
                    <td className="py-3 px-4 text-muted-foreground">
                      {formatDate(course.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/race-planner/courses/${course.id}/generate`)}
                        >
                          Generate Plan
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              disabled={deletingId === course.id}
                            >
                              Delete
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Course</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete "{course.name}"? This will also
                                delete any plans for this course. This cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(course.id)}>
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
