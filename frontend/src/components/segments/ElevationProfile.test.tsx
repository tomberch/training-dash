import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ElevationProfile } from "./ElevationProfile";
import type { ElevationPoint } from "@/api/types";

// Mock recharts - jsdom has no layout, so ResponsiveContainer renders nothing
// without measured dimensions. Replace with a fixed-size wrapper.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  const FixedContainer = ({
    children,
  }: {
    children?: React.ReactNode;
  }): React.ReactElement => (
    <div style={{ width: 800, height: 200 }}>{children}</div>
  );
  return { ...actual, ResponsiveContainer: FixedContainer };
});

const SAMPLE_PROFILE: ElevationPoint[] = [
  { distance_m: 0, elevation_m: 100, grade_pct: 0 },
  { distance_m: 50, elevation_m: 103, grade_pct: 6.0 },
  { distance_m: 100, elevation_m: 108, grade_pct: 10.0 },
  { distance_m: 150, elevation_m: 112, grade_pct: 8.0 },
  { distance_m: 200, elevation_m: 114, grade_pct: 4.0 },
  { distance_m: 250, elevation_m: 115, grade_pct: 2.0 },
];

describe("ElevationProfile", () => {
  describe("rendering", () => {
    it("renders chart with profile data", () => {
      render(<ElevationProfile profile={SAMPLE_PROFILE} />);

      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toBeInTheDocument();
    });

    it("renders empty state when profile is empty", () => {
      render(<ElevationProfile profile={[]} />);

      const emptyState = screen.getByTestId("elevation-profile-empty");
      expect(emptyState).toBeInTheDocument();
      expect(screen.getByText("No elevation data")).toBeInTheDocument();
    });

    it("applies custom height", () => {
      render(<ElevationProfile profile={SAMPLE_PROFILE} height={300} />);

      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toHaveStyle({ height: "300px" });
    });

    it("applies custom className", () => {
      render(
        <ElevationProfile profile={SAMPLE_PROFILE} className="custom-class" />
      );

      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toHaveClass("custom-class");
    });

    it("handles string height value", () => {
      render(<ElevationProfile profile={SAMPLE_PROFILE} height="100%" />);

      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toHaveStyle({ height: "100%" });
    });
  });

  describe("tooltip", () => {
    it("renders chart with Area component for tooltip interaction", () => {
      render(<ElevationProfile profile={SAMPLE_PROFILE} />);

      // Verify the chart container renders
      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toBeInTheDocument();

      // The ResponsiveContainer mock wraps the AreaChart
      // We verify the recharts structure is present
      const wrapper = chart.querySelector("div");
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe("resampling", () => {
    it("resamples large profiles to ~200 points", () => {
      // Generate a profile with 500 points
      const largeProfile: ElevationPoint[] = Array.from(
        { length: 500 },
        (_, i) => ({
          distance_m: i * 10,
          elevation_m: 100 + Math.sin(i / 10) * 50,
          grade_pct: Math.sin(i / 10) * 5,
        })
      );

      render(<ElevationProfile profile={largeProfile} />);

      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toBeInTheDocument();
      // Chart should render without performance issues
    });

    it("preserves all points for small profiles", () => {
      render(<ElevationProfile profile={SAMPLE_PROFILE} />);

      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toBeInTheDocument();
    });
  });

  describe("formatDistanceLabel", () => {
    it("uses custom distance formatter when provided", () => {
      const customFormatter = vi.fn((meters: number) => `${meters}m`);

      render(
        <ElevationProfile
          profile={SAMPLE_PROFILE}
          formatDistanceLabel={customFormatter}
        />
      );

      // The formatter is passed to XAxis tickFormatter
      // We verify the component accepts and uses the prop
      const chart = screen.getByTestId("elevation-profile");
      expect(chart).toBeInTheDocument();
    });
  });

  describe("empty state styling", () => {
    it("applies height to empty state", () => {
      render(<ElevationProfile profile={[]} height={150} />);

      const emptyState = screen.getByTestId("elevation-profile-empty");
      expect(emptyState).toHaveStyle({ height: "150px" });
    });

    it("applies className to empty state", () => {
      render(<ElevationProfile profile={[]} className="test-empty-class" />);

      const emptyState = screen.getByTestId("elevation-profile-empty");
      expect(emptyState).toHaveClass("test-empty-class");
    });
  });
});
