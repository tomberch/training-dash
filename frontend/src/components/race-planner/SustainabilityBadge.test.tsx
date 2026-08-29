import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SustainabilityBadge } from "./SustainabilityBadge";

describe("SustainabilityBadge", () => {
  it("renders nothing when sustainability is null", () => {
    const { container } = render(<SustainabilityBadge sustainability={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders green badge with 'Sustainable' label", () => {
    render(<SustainabilityBadge sustainability="green" />);
    expect(screen.getByText("Sustainable")).toBeInTheDocument();
  });

  it("renders yellow badge with 'Very Hard' label", () => {
    render(<SustainabilityBadge sustainability="yellow" />);
    expect(screen.getByText("Very Hard")).toBeInTheDocument();
  });

  it("renders red badge with 'Beyond Limit' label", () => {
    render(<SustainabilityBadge sustainability="red" />);
    expect(screen.getByText("Beyond Limit")).toBeInTheDocument();
  });

  it("renders compact badge without label", () => {
    render(<SustainabilityBadge sustainability="green" compact />);
    expect(screen.queryByText("Sustainable")).not.toBeInTheDocument();
    // Should still have the colored dot
    expect(document.querySelector(".rounded-full")).toBeInTheDocument();
  });

  it("shows tooltip on hover with description", async () => {
    render(<SustainabilityBadge sustainability="red" />);
    
    const badge = screen.getByText("Beyond Limit");
    await userEvent.hover(badge);
    
    // Tooltip should appear with description
    expect(await screen.findByText(/Beyond your sustainable capability/)).toBeInTheDocument();
  });

  it("applies correct color classes for green", () => {
    render(<SustainabilityBadge sustainability="green" />);
    const badge = screen.getByText("Sustainable").closest("span");
    expect(badge).toHaveClass("bg-success/20", "text-success");
  });

  it("applies correct color classes for yellow", () => {
    render(<SustainabilityBadge sustainability="yellow" />);
    const badge = screen.getByText("Very Hard").closest("span");
    expect(badge).toHaveClass("bg-warning/20", "text-warning");
  });

  it("applies correct color classes for red", () => {
    render(<SustainabilityBadge sustainability="red" />);
    const badge = screen.getByText("Beyond Limit").closest("span");
    expect(badge).toHaveClass("bg-destructive/20", "text-destructive");
  });

  it("renders nothing for unknown sustainability value", () => {
    const { container } = render(<SustainabilityBadge sustainability="unknown" />);
    expect(container).toBeEmptyDOMElement();
  });
});
