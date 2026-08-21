/**
 * Generate Race Plan Form
 *
 * Form for generating race pacing plans with:
 * - Course selection
 * - Bike selection (optional)
 * - Rider parameters (FTP, weight, CP, W')
 * - Plan settings (intensity, optimizer toggle)
 * - Quick preview after generation
 */

import type { JSX } from "react";
import { useState, useEffect, useContext } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { fetchCourses, fetchCourse, generateRacePlan } from "@/api/race-plans";
import { fetchBikes } from "@/api/bikes";
import { fetchThresholds } from "@/api/athlete";
import { UserContext } from "@/contexts/UserContext";
import type {
  CourseListItem,
  CourseDetail,
  Bike,
  GeneratePlanRequest,
  RacePlanResponse,
} from "@/api/types";

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

// =============================================================================
// Course Selector Component
// =============================================================================

interface CourseSelectorProps {
  courses: CourseListItem[];
  selectedCourseId: number | null;
  onSelect: (courseId: number | null) => void;
  loading: boolean;
}

function CourseSelector({ courses, selectedCourseId, onSelect, loading }: CourseSelectorProps): JSX.Element {
  if (loading) {
    return <Skeleton className="h-10 w-full" />;
  }

  if (courses.length === 0) {
    return (
      <div className="p-4 border border-dashed border-border rounded-lg text-center">
        <p className="text-muted-foreground mb-2">No courses yet</p>
        <Link to="/courses/upload" className="text-primary hover:underline text-sm">
          Upload a course
        </Link>
      </div>
    );
  }

  return (
    <select
      value={selectedCourseId ?? ""}
      onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
      className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
    >
      <option value="">Select a course...</option>
      {courses.map((course) => (
        <option key={course.id} value={course.id}>
          {course.name} ({formatDistance(course.distance_m)}, {formatElevation(course.elevation_gain_m)} gain)
        </option>
      ))}
    </select>
  );
}

// =============================================================================
// Bike Selector Component
// =============================================================================

interface BikeSelectorProps {
  bikes: Bike[];
  selectedBikeId: number | null;
  onSelect: (bikeId: number | null) => void;
  loading: boolean;
}

function BikeSelector({ bikes, selectedBikeId, onSelect, loading }: BikeSelectorProps): JSX.Element {
  if (loading) {
    return <Skeleton className="h-10 w-full" />;
  }

  const activeBikes = bikes.filter((b) => b.retired_at === null);

  return (
    <div className="space-y-2">
      <select
        value={selectedBikeId ?? ""}
        onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
        className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        <option value="">Use defaults (road bike)</option>
        {activeBikes.map((bike) => (
          <option key={bike.id} value={bike.id}>
            {bike.name} ({bike.bike_type})
          </option>
        ))}
      </select>
      {selectedBikeId && (
        <BikeDetails bike={activeBikes.find((b) => b.id === selectedBikeId)} />
      )}
      {activeBikes.length === 0 && (
        <p className="text-xs text-muted-foreground">
          <Link to="/gear" className="text-primary hover:underline">
            Add a bike
          </Link>{" "}
          for more accurate predictions
        </p>
      )}
    </div>
  );
}

function BikeDetails({ bike }: { bike: Bike | undefined }): JSX.Element | null {
  if (!bike) return null;

  return (
    <div className="text-xs text-muted-foreground space-y-0.5 pl-1">
      <div>CdA: {bike.cda ? bike.cda.toFixed(3) : "default"}</div>
      <div>Crr: {bike.crr ? bike.crr.toFixed(4) : "default"}</div>
      {bike.calibrated_at && (
        <div className="text-success">Calibrated</div>
      )}
    </div>
  );
}

// =============================================================================
// Intensity Slider Component
// =============================================================================

interface IntensitySliderProps {
  value: number;
  onChange: (value: number) => void;
  ftp: number;
  courseDistanceM?: number;
}

function IntensitySlider({ value, onChange, ftp, courseDistanceM }: IntensitySliderProps): JSX.Element {
  const avgPower = Math.round(ftp * value);
  const intensityLabel = value <= 0.75 ? "Recovery" :
    value <= 0.85 ? "Endurance" :
    value <= 0.95 ? "Tempo" :
    value <= 1.05 ? "Threshold" : "VO2max";

  // Estimate time based on power (simple model: ~30 km/h at 200W on flat)
  // Speed roughly proportional to cube root of power for aerodynamic drag
  const estimatedSpeedKmh = 30 * Math.pow(avgPower / 200, 0.33);
  const estimatedTimeMin = courseDistanceM
    ? Math.round((courseDistanceM / 1000) / estimatedSpeedKmh * 60)
    : null;

  const formatEstimatedTime = (minutes: number): string => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
  };

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium">{(value * 100).toFixed(0)}% of FTP</span>
        <span className="text-sm text-muted-foreground">{avgPower} W avg · {intensityLabel}</span>
      </div>
      <input
        type="range"
        min="0.70"
        max="1.10"
        step="0.01"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>70%</span>
        <span>85%</span>
        <span>100%</span>
        <span>110%</span>
      </div>
      {estimatedTimeMin && (
        <div className="text-sm text-muted-foreground text-center">
          Estimated time: ~{formatEstimatedTime(estimatedTimeMin)}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Quick Preview Component
// =============================================================================

interface QuickPreviewProps {
  result: RacePlanResponse;
  onViewPlan: () => void;
  onGenerateAnother: () => void;
}

function QuickPreview({ result, onViewPlan, onGenerateAnother }: QuickPreviewProps): JSX.Element {
  const improvementText = result.comparison.improvement_vs_constant_pct
    ? `${result.comparison.improvement_vs_constant_pct.toFixed(1)}% faster than constant power`
    : null;

  return (
    <div className="bg-success/10 border border-success/20 rounded-xl p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-success">Plan Generated!</h3>
          {improvementText && (
            <p className="text-sm text-success/80 mt-1">{improvementText}</p>
          )}
        </div>
        <svg className="w-8 h-8 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center">
          <div className="text-2xl font-bold">{result.total_time_formatted}</div>
          <div className="text-xs text-muted-foreground">Total Time</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold">{Math.round(result.avg_power_w)} W</div>
          <div className="text-xs text-muted-foreground">Avg Power</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold">
            {result.intensity_factor ? result.intensity_factor.toFixed(2) : "—"}
          </div>
          <div className="text-xs text-muted-foreground">IF</div>
        </div>
      </div>

      {result.warnings.length > 0 && (
        <div className="bg-warning/10 border border-warning/20 rounded-lg p-3 mb-4 text-sm">
          <span className="font-medium text-warning">Note: </span>
          <span className="text-warning/80">{result.warnings.join(", ")}</span>
        </div>
      )}

      <div className="flex gap-3">
        <Button onClick={onViewPlan} className="flex-1">
          View Full Plan
        </Button>
        <Button variant="outline" onClick={onGenerateAnother}>
          Generate Another
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function GeneratePlan(): JSX.Element {
  const { courseId: courseIdParam } = useParams<{ courseId?: string }>();
  const navigate = useNavigate();
  const userContext = useContext(UserContext);
  const user = userContext?.user;

  // Data state
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [bikes, setBikes] = useState<Bike[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<CourseDetail | null>(null);
  const [loadingData, setLoadingData] = useState(true);

  // Form state
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(
    courseIdParam ? Number(courseIdParam) : null
  );
  const [selectedBikeId, setSelectedBikeId] = useState<number | null>(null);
  const [ftp, setFtp] = useState<string>("250");
  const [weight, setWeight] = useState<string>("");
  const [cp, setCp] = useState<string>("");
  const [wPrime, setWPrime] = useState<string>("");
  const [targetIntensity, setTargetIntensity] = useState(0.85);
  const [useOptimizer, setUseOptimizer] = useState(false);
  const [planName, setPlanName] = useState("");

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<RacePlanResponse | null>(null);

  // Load initial data
  useEffect(() => {
    setLoadingData(true);
    Promise.all([
      fetchCourses(),
      fetchBikes(),
      fetchThresholds(),
    ])
      .then(([coursesData, bikesData, thresholdsData]) => {
        setCourses(coursesData);
        setBikes(bikesData);

        // Set FTP from latest threshold
        if (thresholdsData.length > 0) {
          const latestFtp = thresholdsData[0].ftp_watts;
          if (latestFtp) setFtp(latestFtp.toString());
        }

        // Set weight from user profile
        if (user?.weight_kg) {
          setWeight(user.weight_kg.toString());
        }

        // Set default bike
        const defaultBike = bikesData.find((b) => b.is_default && !b.retired_at);
        if (defaultBike) {
          setSelectedBikeId(defaultBike.id);
        }
      })
      .catch((err) => {
        toast.error(err.message || "Failed to load data");
      })
      .finally(() => setLoadingData(false));
  }, [user]);

  // Load selected course details
  useEffect(() => {
    if (selectedCourseId) {
      fetchCourse(selectedCourseId)
        .then(setSelectedCourse)
        .catch(() => setSelectedCourse(null));
    } else {
      setSelectedCourse(null);
    }
  }, [selectedCourseId]);

  // Handle course selection from URL param
  useEffect(() => {
    if (courseIdParam) {
      setSelectedCourseId(Number(courseIdParam));
    }
  }, [courseIdParam]);

  const handleGenerate = async () => {
    if (!selectedCourseId) {
      toast.error("Please select a course");
      return;
    }

    const ftpValue = parseInt(ftp);
    if (isNaN(ftpValue) || ftpValue < 100 || ftpValue > 600) {
      toast.error("FTP must be between 100 and 600 watts");
      return;
    }

    setGenerating(true);
    setResult(null);

    const request: GeneratePlanRequest = {
      course_id: selectedCourseId,
      ftp_watts: ftpValue,
      target_intensity: targetIntensity,
      use_optimizer: useOptimizer,
    };

    if (selectedBikeId) request.bike_id = selectedBikeId;
    if (weight) request.rider_weight_kg = parseFloat(weight);
    // Apply defaults for CP and W' when not specified
    request.cp_watts = cp ? parseInt(cp) : Math.round(ftpValue * 0.95);
    request.w_prime_joules = wPrime ? parseInt(wPrime) : 20000;
    if (planName.trim()) request.name = planName.trim();

    try {
      const planResult = await generateRacePlan(request);
      setResult(planResult);
      toast.success("Plan generated successfully!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to generate plan");
    } finally {
      setGenerating(false);
    }
  };

  const handleViewPlan = () => {
    if (result) {
      navigate(`/race-planner/plans/${result.id}`);
    }
  };

  const handleGenerateAnother = () => {
    setResult(null);
  };

  // Show preview if we have a result
  if (result) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <button
          onClick={() => navigate("/race-planner")}
          className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline mb-6"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Race Planner
        </button>

        <QuickPreview
          result={result}
          onViewPlan={handleViewPlan}
          onGenerateAnother={handleGenerateAnother}
        />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate("/race-planner")}
          className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline mb-4"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Race Planner
        </button>

        <h1 className="text-page-title">Generate Race Plan</h1>
        <p className="text-page-subtitle mt-1">
          Create a pacing strategy optimized for your course and fitness
        </p>
      </div>

      <div className="space-y-8">
        {/* Course Selection */}
        <section className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-card-title mb-4">Course</h2>
          <CourseSelector
            courses={courses}
            selectedCourseId={selectedCourseId}
            onSelect={setSelectedCourseId}
            loading={loadingData}
          />
          {selectedCourse && (
            <div className="mt-4 p-3 bg-muted/50 rounded-lg">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{selectedCourse.name}</span>
                <span className="text-muted-foreground">
                  {formatDistance(selectedCourse.distance_m)} · {formatElevation(selectedCourse.elevation_gain_m)} gain
                </span>
              </div>
              {selectedCourse.climbs.length > 0 && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {selectedCourse.climbs.length} climb{selectedCourse.climbs.length !== 1 ? "s" : ""} detected
                </div>
              )}
            </div>
          )}
        </section>

        {/* Bike Selection */}
        <section className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-card-title mb-4">Bike</h2>
          <BikeSelector
            bikes={bikes}
            selectedBikeId={selectedBikeId}
            onSelect={setSelectedBikeId}
            loading={loadingData}
          />
        </section>

        {/* Rider Parameters */}
        <section className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-card-title mb-4">Rider Parameters</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="ftp">FTP (watts) *</Label>
              <Input
                id="ftp"
                type="number"
                value={ftp}
                onChange={(e) => setFtp(e.target.value)}
                min={100}
                max={600}
                placeholder="250"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="weight">Weight (kg)</Label>
              <Input
                id="weight"
                type="number"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                min={30}
                max={200}
                step={0.1}
                placeholder="75"
              />
              <p className="text-caption">Optional, defaults to profile</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cp">CP (watts)</Label>
              <Input
                id="cp"
                type="number"
                value={cp}
                onChange={(e) => setCp(e.target.value)}
                min={100}
                max={600}
                placeholder={ftp ? `${Math.round(parseInt(ftp) * 0.95)}` : ""}
              />
              <p className="text-caption">Optional, defaults to 95% of FTP</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wprime">W' (joules)</Label>
              <Input
                id="wprime"
                type="number"
                value={wPrime}
                onChange={(e) => setWPrime(e.target.value)}
                min={5000}
                max={50000}
                step={1000}
                placeholder="20000"
              />
              <p className="text-caption">Optional, defaults to 20kJ</p>
            </div>
          </div>
        </section>

        {/* Plan Settings */}
        <section className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-card-title mb-4">Plan Settings</h2>

          <div className="space-y-6">
            <div className="space-y-1.5">
              <Label htmlFor="name">Plan Name</Label>
              <Input
                id="name"
                type="text"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                placeholder="Race Day Plan"
                maxLength={200}
              />
            </div>

            <div>
              <Label className="mb-3 block">Target Intensity</Label>
              <IntensitySlider
                value={targetIntensity}
                onChange={setTargetIntensity}
                ftp={parseInt(ftp) || 250}
                courseDistanceM={selectedCourse?.distance_m}
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
              <div>
                <Label htmlFor="optimizer" className="text-sm font-medium">
                  Use Optimizer
                </Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  More accurate, takes 10-30 seconds
                </p>
              </div>
              <Switch
                id="optimizer"
                checked={useOptimizer}
                onCheckedChange={setUseOptimizer}
              />
            </div>
          </div>
        </section>

        {/* Generate Button */}
        <Button
          onClick={handleGenerate}
          disabled={!selectedCourseId || generating}
          className="w-full h-12 text-lg"
        >
          {generating ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {useOptimizer ? "Optimizing..." : "Generating..."}
            </span>
          ) : (
            "Generate Plan"
          )}
        </Button>
      </div>
    </div>
  );
}
