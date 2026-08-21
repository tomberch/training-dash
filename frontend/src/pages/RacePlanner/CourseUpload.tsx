/**
 * Course Upload Page
 *
 * Upload GPX or FIT files to create race courses:
 * - Drag-and-drop file zone
 * - Client-side GPX parsing for preview
 * - Map preview of the course
 * - Basic metrics display
 * - Name input and submit
 */

import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { uploadCourse } from "@/api/race-plans";

// =============================================================================
// Types
// =============================================================================

interface ParsedCourse {
  name: string;
  coordinates: [number, number][]; // [lat, lon]
  distance_m: number;
  elevation_gain_m: number;
  elevation_loss_m: number;
  min_elevation_m: number;
  max_elevation_m: number;
}

// =============================================================================
// GPX Parser (client-side preview)
// =============================================================================

function parseGPX(content: string): ParsedCourse | null {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(content, "text/xml");

    // Check for parse errors
    const parseError = doc.querySelector("parsererror");
    if (parseError) return null;


    // Try to get name from metadata or track
    const nameEl = doc.querySelector("metadata > name") || doc.querySelector("trk > name");
    const name = nameEl?.textContent || "Untitled Course";

    // Extract track points
    const trkpts = doc.querySelectorAll("trkpt");
    if (trkpts.length < 2) return null;

    const coordinates: [number, number][] = [];
    const elevations: number[] = [];

    trkpts.forEach((pt) => {
      const lat = parseFloat(pt.getAttribute("lat") || "0");
      const lon = parseFloat(pt.getAttribute("lon") || "0");
      const eleEl = pt.querySelector("ele");
      const ele = eleEl ? parseFloat(eleEl.textContent || "0") : 0;

      coordinates.push([lat, lon]);
      elevations.push(ele);
    });

    // Calculate distance using Haversine
    let distance_m = 0;
    for (let i = 1; i < coordinates.length; i++) {
      distance_m += haversineDistance(
        coordinates[i - 1][0], coordinates[i - 1][1],
        coordinates[i][0], coordinates[i][1]
      );
    }

    // Calculate elevation stats
    let elevation_gain_m = 0;
    let elevation_loss_m = 0;
    for (let i = 1; i < elevations.length; i++) {
      const diff = elevations[i] - elevations[i - 1];
      if (diff > 0) elevation_gain_m += diff;
      else elevation_loss_m += Math.abs(diff);
    }

    return {
      name,
      coordinates,
      distance_m,
      elevation_gain_m,
      elevation_loss_m,
      min_elevation_m: Math.min(...elevations),
      max_elevation_m: Math.max(...elevations),
    };
  } catch {
    return null;
  }
}


function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

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

const ACCEPTED_EXTENSIONS = [".gpx", ".fit"];

function isValidFile(file: File): boolean {
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  return ACCEPTED_EXTENSIONS.includes(ext);
}


// =============================================================================
// Course Preview Map (SVG-based)
// =============================================================================

interface CoursePreviewMapProps {
  coordinates: [number, number][];
  className?: string;
}

function CoursePreviewMap({ coordinates, className }: CoursePreviewMapProps) {
  if (coordinates.length < 2) {
    return (
      <div className={cn("bg-muted rounded-lg flex items-center justify-center", className)}>
        <span className="text-muted-foreground">No route data</span>
      </div>
    );
  }

  // Find bounding box
  let minLat = Infinity, maxLat = -Infinity;
  let minLon = Infinity, maxLon = -Infinity;
  for (const [lat, lon] of coordinates) {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }

  // Add padding
  const latPad = (maxLat - minLat) * 0.1 || 0.001;
  const lonPad = (maxLon - minLon) * 0.1 || 0.001;
  minLat -= latPad;
  maxLat += latPad;
  minLon -= lonPad;
  maxLon += lonPad;

  const width = 400;
  const height = 250;

  // Scale coordinates to SVG
  const latRange = maxLat - minLat;
  const lonRange = maxLon - minLon;

  const toSvg = (lat: number, lon: number): [number, number] => {
    const x = ((lon - minLon) / lonRange) * width;
    const y = ((maxLat - lat) / latRange) * height;
    return [x, y];
  };

  // Build path
  const pathParts: string[] = [];
  const [startX, startY] = toSvg(coordinates[0][0], coordinates[0][1]);
  pathParts.push(`M ${startX.toFixed(1)} ${startY.toFixed(1)}`);
  for (let i = 1; i < coordinates.length; i++) {
    const [x, y] = toSvg(coordinates[i][0], coordinates[i][1]);
    pathParts.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  const path = pathParts.join(" ");
  const [endX, endY] = toSvg(
    coordinates[coordinates.length - 1][0],
    coordinates[coordinates.length - 1][1]
  );


  return (
    <div className={cn("bg-muted rounded-lg overflow-hidden", className)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
        {/* Route shadow */}
        <path
          d={path}
          fill="none"
          stroke="white"
          strokeWidth={4}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.5}
        />
        {/* Route */}
        <path
          d={path}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Start marker */}
        <circle cx={startX} cy={startY} r={6} fill="#10b981" stroke="white" strokeWidth={2} />
        {/* End marker */}
        <circle cx={endX} cy={endY} r={6} fill="#ef4444" stroke="white" strokeWidth={2} />
      </svg>
    </div>
  );
}


// =============================================================================
// Drop Zone Component
// =============================================================================

interface DropZoneProps {
  onFileSelect: (file: File) => void;
  onInvalidFile?: () => void;
  disabled?: boolean;
}

function DropZone({ onFileSelect, onInvalidFile, disabled }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (disabled) return;

    const file = e.dataTransfer.files[0];
    if (file) {
      if (isValidFile(file)) {
        onFileSelect(file);
      } else {
        onInvalidFile?.();
      }
    }
  }, [disabled, onFileSelect, onInvalidFile]);

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (isValidFile(file)) {
        onFileSelect(file);
      } else {
        onInvalidFile?.();
      }
    }
  };

  return (
    <div
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
        isDragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".gpx,.fit"
        onChange={handleInputChange}
        className="hidden"
        disabled={disabled}
      />
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
          <svg className="w-6 h-6 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        <div>
          <p className="font-medium">Drop your course file here</p>
          <p className="text-sm text-muted-foreground mt-1">
            or click to browse · GPX or FIT files
          </p>
        </div>
      </div>
    </div>
  );
}


// =============================================================================
// Metric Card
// =============================================================================

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 text-center">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export function CourseUpload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [parsedCourse, setParsedCourse] = useState<ParsedCourse | null>(null);
  const [courseName, setCourseName] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const handleFileSelect = useCallback(async (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    setWarnings([]);
    setParsedCourse(null);

    // Only parse GPX files client-side (FIT is binary)
    if (selectedFile.name.toLowerCase().endsWith(".gpx")) {
      setIsParsing(true);
      try {
        const content = await selectedFile.text();
        const parsed = parseGPX(content);
        if (parsed) {
          setParsedCourse(parsed);
          setCourseName(parsed.name);
        } else {
          setError("Could not parse GPX file. The file may be corrupted or in an unsupported format.");
        }
      } catch {
        setError("Failed to read file");
      } finally {
        setIsParsing(false);
      }
    } else {
      // FIT file - use filename as default name
      const baseName = selectedFile.name.replace(/\.[^.]+$/, "");
      setCourseName(baseName);
    }
  }, []);


  const handleSubmit = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const result = await uploadCourse(file, courseName || undefined);
      setWarnings(result.warnings);

      // Navigate to course detail page
      navigate(`/race-planner/courses/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    setParsedCourse(null);
    setCourseName("");
    setError(null);
    setWarnings([]);
  };

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
        <h1 className="text-page-title">Upload Course</h1>
        <p className="text-page-subtitle mt-1">
          Import a GPX or FIT file to create a race course
        </p>
      </div>


      {/* Error display */}
      {error && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          {error}
        </div>
      )}

      {/* Warnings display */}
      {warnings.length > 0 && (
        <div className="mb-6 p-4 bg-warning/10 text-warning rounded-lg border border-warning/20">
          <ul className="list-disc list-inside space-y-1">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* File drop zone (shown when no file selected) */}
      {!file && (
        <DropZone
          onFileSelect={handleFileSelect}
          onInvalidFile={() => setError("Please select a GPX or FIT file")}
          disabled={isUploading}
        />
      )}

      {/* File selected - show preview and form */}
      {file && (
        <div className="space-y-6">
          {/* File info card */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div>
                  <div className="font-medium">{file.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </div>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={handleClear} disabled={isUploading}>
                Change file
              </Button>
            </div>


            {/* Map preview (GPX only) */}
            {isParsing ? (
              <Skeleton className="h-48 w-full rounded-lg mb-4" />
            ) : parsedCourse ? (
              <CoursePreviewMap
                coordinates={parsedCourse.coordinates}
                className="h-48 mb-4"
              />
            ) : file.name.toLowerCase().endsWith(".fit") ? (
              <div className="h-48 bg-muted rounded-lg flex items-center justify-center mb-4">
                <span className="text-muted-foreground">
                  Preview available after upload
                </span>
              </div>
            ) : null}

            {/* Metrics (GPX only) */}
            {parsedCourse && (
              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="Distance" value={formatDistance(parsedCourse.distance_m)} />
                <MetricCard label="Elevation Gain" value={formatElevation(parsedCourse.elevation_gain_m)} />
                <MetricCard label="Min Elevation" value={formatElevation(parsedCourse.min_elevation_m)} />
                <MetricCard label="Max Elevation" value={formatElevation(parsedCourse.max_elevation_m)} />
              </div>
            )}
          </div>

          {/* Name input */}
          <div className="space-y-2">
            <Label htmlFor="courseName">Course Name</Label>
            <Input
              id="courseName"
              value={courseName}
              onChange={(e) => setCourseName(e.target.value)}
              placeholder="Enter a name for this course"
              disabled={isUploading}
            />
            <p className="text-caption">
              Leave blank to use the name from the file
            </p>
          </div>

          {/* Submit button */}
          <div className="flex gap-3">
            <Button
              onClick={handleSubmit}
              disabled={isUploading}
              className="flex-1"
            >
              {isUploading ? "Uploading..." : "Create Course"}
            </Button>
            <Button
              variant="outline"
              onClick={handleClear}
              disabled={isUploading}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
