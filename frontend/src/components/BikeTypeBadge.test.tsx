import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BikeTypeBadge } from "./BikeTypeBadge";

describe("BikeTypeBadge", () => {
  it("renders bike type label", () => {
    render(<BikeTypeBadge type="road" />);
    expect(screen.getByText("Road")).toBeInTheDocument();
  });

  it("renders gravel type", () => {
    render(<BikeTypeBadge type="gravel" />);
    expect(screen.getByText("Gravel")).toBeInTheDocument();
  });

  it("renders MTB type", () => {
    render(<BikeTypeBadge type="mtb" />);
    expect(screen.getByText("MTB")).toBeInTheDocument();
  });

  it("renders TT/Tri type", () => {
    render(<BikeTypeBadge type="tt" />);
    expect(screen.getByText("TT/Tri")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(<BikeTypeBadge type="road" className="custom-class" />);
    const badge = screen.getByText("Road");
    expect(badge).toHaveClass("custom-class");
  });

  it("has rounded-full class for pill shape", () => {
    render(<BikeTypeBadge type="road" />);
    const badge = screen.getByText("Road");
    expect(badge).toHaveClass("rounded-full");
  });
});
