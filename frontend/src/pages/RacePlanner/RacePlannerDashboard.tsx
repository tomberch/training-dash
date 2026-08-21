/**
 * Race Planner Dashboard
 *
 * Landing page for the Race Planner feature:
 * - Quick stats (courses, plans)
 * - Recent courses and plans
 * - Quick action buttons
 * - Getting started guide for new users
 */

import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchCourses, fetchRacePlans } from "@/api/race-plans";
import type { CourseListItem, RacePlanListItem } from "@/api/types";
import { formatDistance, formatElevation, formatDateShort } from "./utils";


// =============================================================================
// Stat Card Component
// =============================================================================

function StatCard({
  label,
  value,
  icon,
  href,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  href: string;
}) {
  return (
    <Link
      to={href}
      className="bg-card border border-border rounded-xl p-6 hover:bg-muted/30 transition-colors"
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-3xl font-bold">{value}</div>
          <div className="text-sm text-muted-foreground mt-1">{label}</div>
        </div>
        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
      </div>
    </Link>
  );
}

// =============================================================================
// Recent Course Card
// =============================================================================

function RecentCourseCard({ course }: { course: CourseListItem }) {
  return (
    <Link
      to={`/race-planner/courses/${course.id}`}
      className="flex items-center justify-between p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>
        <div>
          <div className="font-medium text-sm">{course.name}</div>
          <div className="text-xs text-muted-foreground">
            {formatDistance(course.distance_m)} · {formatElevation(course.elevation_gain_m)} gain
          </div>
        </div>
      </div>
      <span className="text-xs text-muted-foreground">{formatDateShort(course.created_at)}</span>
    </Link>
  );
}


// =============================================================================
// Recent Plan Card
// =============================================================================

function RecentPlanCard({ plan }: { plan: RacePlanListItem }) {
  return (
    <Link
      to={`/race-planner/plans/${plan.id}`}
      className="flex items-center justify-between p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-success/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <div className="font-medium text-sm">{plan.name || "Untitled Plan"}</div>
          <div className="text-xs text-muted-foreground">
            {plan.total_time_formatted} · {Math.round(plan.avg_power_w)} W avg
          </div>
        </div>
      </div>
      <span className="text-xs text-muted-foreground">{formatDateShort(plan.created_at)}</span>
    </Link>
  );
}

// =============================================================================
// Empty State / Getting Started
// =============================================================================

function GettingStarted() {
  const navigate = useNavigate();

  return (
    <div className="bg-card border border-border rounded-xl p-8 text-center">
      <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
      </div>
      <h2 className="text-xl font-semibold mb-2">Get Started with Race Planner</h2>
      <p className="text-muted-foreground mb-6 max-w-md mx-auto">
        Upload a GPX or FIT course file, then generate an optimized pacing plan
        based on your fitness and the terrain.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Button onClick={() => navigate("/race-planner/courses/new")}>
          Upload Course
        </Button>
        <Button variant="outline" onClick={() => navigate("/race-planner/courses")}>
          Browse Courses
        </Button>
      </div>

      <div className="mt-8 pt-6 border-t border-border">
        <h3 className="text-sm font-medium mb-4">How it works</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-left">
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-medium flex-shrink-0">
              1
            </div>
            <div>
              <div className="font-medium text-sm">Upload Course</div>
              <div className="text-xs text-muted-foreground">Import GPX or FIT file</div>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-medium flex-shrink-0">
              2
            </div>
            <div>
              <div className="font-medium text-sm">Generate Plan</div>
              <div className="text-xs text-muted-foreground">Set FTP and target intensity</div>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-medium flex-shrink-0">
              3
            </div>
            <div>
              <div className="font-medium text-sm">Execute & Compare</div>
              <div className="text-xs text-muted-foreground">Review pacing after the ride</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


// =============================================================================
// Main Component
// =============================================================================

export function RacePlannerDashboard() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [plans, setPlans] = useState<RacePlanListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([fetchCourses(), fetchRacePlans()])
      .then(([coursesData, plansData]) => {
        setCourses(coursesData);
        setPlans(plansData);
      })
      .catch(() => {
        // Silently fail, show empty state
      })
      .finally(() => setIsLoading(false));
  }, []);

  const recentCourses = courses.slice(0, 5);
  const recentPlans = plans.slice(0, 5);
  const hasData = courses.length > 0 || plans.length > 0;

  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-64 mb-8" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-page-title">Race Planner</h1>
          <p className="text-page-subtitle mt-1">
            Create and manage pacing plans for your courses
          </p>
        </div>
        <Button onClick={() => navigate("/race-planner/courses/new")}>
          Upload Course
        </Button>
      </div>

      {!hasData ? (
        <GettingStarted />
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <StatCard
              label="Courses"
              value={courses.length}
              href="/race-planner/courses"
              icon={
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
              }
            />
            <StatCard
              label="Plans"
              value={plans.length}
              href="/race-planner/plans"
              icon={
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              }
            />
          </div>


          {/* Recent Items */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Courses */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-card-title">Recent Courses</h2>
                <Link
                  to="/race-planner/courses"
                  className="text-sm text-primary hover:underline"
                >
                  View all
                </Link>
              </div>
              {recentCourses.length > 0 ? (
                <div className="space-y-2">
                  {recentCourses.map((course) => (
                    <RecentCourseCard key={course.id} course={course} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-muted-foreground">
                  <p className="mb-2">No courses yet</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate("/race-planner/courses/new")}
                  >
                    Upload Course
                  </Button>
                </div>
              )}
            </div>

            {/* Recent Plans */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-card-title">Recent Plans</h2>
                <Link
                  to="/race-planner/plans"
                  className="text-sm text-primary hover:underline"
                >
                  View all
                </Link>
              </div>
              {recentPlans.length > 0 ? (
                <div className="space-y-2">
                  {recentPlans.map((plan) => (
                    <RecentPlanCard key={plan.id} plan={plan} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-muted-foreground">
                  <p className="mb-2">No plans yet</p>
                  {courses.length > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate("/race-planner/generate")}
                    >
                      Generate Plan
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
