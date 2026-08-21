/**
 * Race Plans API - CRUD operations for race pacing plans
 */
import { apiGet, apiPost, apiDelete } from "./base";
import type {
  RacePlanListItem,
  RacePlanDetail,
  RacePlanResponse,
  GeneratePlanRequest,
  CourseDetail,
  CourseListItem,
  ExecutionComparison,
  MatchingActivity,
} from "./types";

/**
 * Fetch all race plans for the current user.
 * @param courseId - Optional filter by course ID
 * @param limit - Maximum number of plans to return
 */
export async function fetchRacePlans(
  courseId?: number,
  limit = 20
): Promise<RacePlanListItem[]> {
  const params = new URLSearchParams();
  if (courseId !== undefined) params.set("course_id", String(courseId));
  if (limit !== 20) params.set("limit", String(limit));
  const query = params.toString();
  return apiGet<RacePlanListItem[]>(`/race-plans${query ? `?${query}` : ""}`);
}

/**
 * Fetch a single race plan by ID with full details.
 */
export async function fetchRacePlan(planId: number): Promise<RacePlanDetail> {
  return apiGet<RacePlanDetail>(`/race-plans/${planId}`);
}

/**
 * Generate a new race plan.
 */
export async function generateRacePlan(
  request: GeneratePlanRequest
): Promise<RacePlanResponse> {
  return apiPost<RacePlanResponse>("/race-plans", request, "Failed to generate race plan");
}

/**
 * Delete a race plan.
 */
export async function deleteRacePlan(planId: number): Promise<void> {
  return apiDelete(`/race-plans/${planId}`, "Failed to delete race plan");
}

/**
 * Regenerate a plan with updated parameters.
 */
export async function regenerateRacePlan(
  planId: number,
  updates?: Partial<GeneratePlanRequest>
): Promise<RacePlanResponse> {
  return apiPost<RacePlanResponse>(
    `/race-plans/${planId}/regenerate`,
    updates,
    "Failed to regenerate race plan"
  );
}

/**
 * Fetch course details (for displaying alongside plan).
 */
export async function fetchCourse(courseId: number): Promise<CourseDetail> {
  return apiGet<CourseDetail>(`/courses/${courseId}`);
}

/**
 * Fetch all courses for the current user.
 */
export async function fetchCourses(): Promise<CourseListItem[]> {
  return apiGet<CourseListItem[]>("/courses");
}



/**
 * Compare an executed activity against a race plan.
 */
export async function compareExecution(
  planId: number,
  activityId: string
): Promise<ExecutionComparison> {
  return apiPost<ExecutionComparison>(
    `/race-plans/${planId}/compare`,
    { activity_id: activityId },
    "Failed to compare execution"
  );
}

/**
 * Fetch activities that can be compared to a plan.
 * Returns activities with power data and similar distance to the course.
 */
export async function fetchMatchingActivities(
  planId: number
): Promise<MatchingActivity[]> {
  return apiGet<MatchingActivity[]>(`/race-plans/${planId}/matching-activities`);
}
