import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CourseUpload } from "./CourseUpload";
import * as racePlansApi from "@/api/race-plans";
import type { CourseUploadResponse } from "@/api/types";

vi.mock("@/api/race-plans");

const mockUploadCourse = vi.mocked(racePlansApi.uploadCourse);

const mockUploadResponse: CourseUploadResponse = {
  id: 1,
  name: "Test Course",
  source_type: "gpx",
  source_filename: "test.gpx",
  distance_m: 50000,
  elevation_gain_m: 800,
  elevation_loss_m: 750,
  min_elevation_m: 50,
  max_elevation_m: 350,
  created_at: "2025-02-01T12:00:00Z",
  warnings: [],
};

function renderCourseUpload() {
  return render(
    <MemoryRouter initialEntries={["/race-planner/upload"]}>
      <Routes>
        <Route path="/race-planner/upload" element={<CourseUpload />} />
        <Route
          path="/race-planner/courses/:courseId"
          element={<div data-testid="course-detail">Course Detail</div>}
        />
        <Route
          path="/race-planner"
          element={<div data-testid="race-planner">Race Planner</div>}
        />
      </Routes>
    </MemoryRouter>
  );
}

// Helper to create a mock GPX file
function createGpxFile(name: string = "test.gpx", content?: string): File {
  const gpxContent = content || `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1">
  <metadata>
    <name>Test Course</name>
  </metadata>
  <trk>
    <name>Test Track</name>
    <trkseg>
      <trkpt lat="51.5074" lon="-0.1278"><ele>10</ele></trkpt>
      <trkpt lat="51.5084" lon="-0.1268"><ele>15</ele></trkpt>
      <trkpt lat="51.5094" lon="-0.1258"><ele>20</ele></trkpt>
      <trkpt lat="51.5104" lon="-0.1248"><ele>25</ele></trkpt>
      <trkpt lat="51.5114" lon="-0.1238"><ele>30</ele></trkpt>
    </trkseg>
  </trk>
</gpx>`;

  return new File([gpxContent], name, { type: "application/gpx+xml" });
}

// Helper to create a mock FIT file
function createFitFile(name: string = "test.fit"): File {
  // FIT files are binary, just create a minimal mock
  const content = new Uint8Array([0x0e, 0x10, 0x00, 0x00]); // FIT header bytes
  return new File([content], name, { type: "application/octet-stream" });
}

// Helper to upload a file using the hidden input
async function uploadFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  if (!input) {
    throw new Error("File input not found");
  }

  // Use fireEvent.change directly as userEvent.upload can be problematic
  Object.defineProperty(input, "files", {
    value: [file],
    configurable: true,
  });
  fireEvent.change(input);
}

describe("CourseUpload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUploadCourse.mockResolvedValue(mockUploadResponse);
  });

  describe("Initial Rendering", () => {
    it("renders page title and description", () => {
      renderCourseUpload();

      expect(screen.getByText("Create Course")).toBeInTheDocument();
      expect(
        screen.getByText(/Upload a file or use an existing activity/)
      ).toBeInTheDocument();
    });

    it("renders drop zone", () => {
      renderCourseUpload();

      expect(screen.getByText("Drop your course file here")).toBeInTheDocument();
      expect(screen.getByText(/or click to browse/)).toBeInTheDocument();
      expect(screen.getByText(/GPX or FIT files/)).toBeInTheDocument();
    });

    it("renders back button", () => {
      renderCourseUpload();

      expect(screen.getByText("Back to Race Planner")).toBeInTheDocument();
    });

    it("has hidden file input", () => {
      renderCourseUpload();

      const input = document.querySelector('input[type="file"]');
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute("accept", ".gpx,.fit");
    });
  });

  describe("File Selection", () => {
    it("accepts GPX file and shows filename", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });
    });

    it("accepts FIT file and shows filename", async () => {
      renderCourseUpload();

      const file = createFitFile("my_ride.fit");
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("my_ride.fit")).toBeInTheDocument();
      });
    });

    it("shows Change file button after selection", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("Change file")).toBeInTheDocument();
      });
    });
  });

  describe("GPX Preview", () => {
    it("pre-fills course name from GPX metadata", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        // Check for the name input being pre-filled
        const nameInput = screen.getByLabelText("Course Name");
        expect(nameInput).toHaveValue("Test Course");
      });
    });

    it("displays distance metric", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("Distance")).toBeInTheDocument();
      });
    });

    it("displays elevation gain metric", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("Elevation Gain")).toBeInTheDocument();
      });
    });
  });

  describe("FIT File Handling", () => {
    it("uses filename (without extension) as default name", async () => {
      renderCourseUpload();

      const file = createFitFile("my_ride.fit");
      await uploadFile(file);

      await waitFor(() => {
        const nameInput = screen.getByLabelText("Course Name");
        expect(nameInput).toHaveValue("my_ride");
      });
    });

    it("shows placeholder for preview", async () => {
      renderCourseUpload();

      const file = createFitFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("Preview available after upload")).toBeInTheDocument();
      });
    });
  });

  describe("Form Submission", () => {
    it("calls uploadCourse on submit", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Create Course" }));

      await waitFor(() => {
        expect(mockUploadCourse).toHaveBeenCalledWith(file, "Test Course");
      });
    });

    it("shows loading state during upload", async () => {
      mockUploadCourse.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockUploadResponse), 200))
      );
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Create Course" }));

      await waitFor(() => {
        expect(screen.getByText("Uploading...")).toBeInTheDocument();
      });
    });

    it("navigates to course detail on success", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Create Course" }));

      await waitFor(() => {
        expect(screen.getByTestId("course-detail")).toBeInTheDocument();
      });
    });
  });

  describe("Error Handling", () => {
    it("shows error when upload fails", async () => {
      mockUploadCourse.mockRejectedValue(new Error("Upload failed"));
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Create Course" }));

      await waitFor(() => {
        expect(screen.getByText("Upload failed")).toBeInTheDocument();
      });
    });

    it("shows error for invalid GPX content", async () => {
      renderCourseUpload();

      const invalidGpx = new File(["not valid xml"], "test.gpx", {
        type: "application/gpx+xml",
      });
      await uploadFile(invalidGpx);

      await waitFor(() => {
        expect(screen.getByText(/Could not parse GPX file/)).toBeInTheDocument();
      });
    });
  });

  describe("Cancel Flow", () => {
    it("clears file when Cancel clicked", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

      await waitFor(() => {
        expect(screen.getByText("Drop your course file here")).toBeInTheDocument();
        expect(screen.queryByText("test.gpx")).not.toBeInTheDocument();
      });
    });

    it("clears file when Change file clicked", async () => {
      renderCourseUpload();

      const file = createGpxFile();
      await uploadFile(file);

      await waitFor(() => {
        expect(screen.getByText("test.gpx")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByText("Change file"));

      await waitFor(() => {
        expect(screen.getByText("Drop your course file here")).toBeInTheDocument();
      });
    });
  });

  describe("Back Navigation", () => {
    it("back button navigates to race planner", async () => {
      renderCourseUpload();

      await userEvent.click(screen.getByText("Back to Race Planner"));

      await waitFor(() => {
        expect(screen.getByTestId("race-planner")).toBeInTheDocument();
      });
    });
  });
});
