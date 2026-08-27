# Pacing Model Consolidation and Curvature Physics

Status: Accepted

## Context

The pacing feature (race planner) grew a grade-power formula duplicated in 4 places, Normalized Power in 5 implementations, two `PacingCoefficients` dataclasses with hand-copied fields, defaults hardcoded in 5 modules, and a curvature mismatch: calibration fits a Menger curvature coefficient (1/m) from real rides, but runtime speed reduction uses hardcoded bearing-curvature threshold tables (deg/100m) that ignore the fitted coefficient. Two of five calibrated coefficients are dead at runtime, and validation shows 15–42% speed errors on mountain courses. Separately, the per-segment wind path in `GenerateRacePlan` passes `headwind_mps` to a dataclass whose field is `wind_speed_mps` (crash for any plan with wind), and the fine-grained (~25m) pacing path silently ignores per-segment wind.

## Decision

**Phase A — consolidation (behavior-preserving).** One power model: a new `domain/pacing_model.py` becomes the single home of `PacingCoefficients`, the grade-power formula, clamp constants, one core Normalized Power implementation (VI-correction and variable-target expansion become wrappers), ride-type resolution, and all defaults. `fine_grained_pacing.py` shrinks to geometry (resampling, curvature) and the per-point physics loop, importing the formula instead of re-implementing it. The coefficients repository becomes the sole adapter at the DB seam (`from_db_model`/`to_db_model`); the second dataclass, `DBPacingCoefficients` alias hack, and hand-copied field lists die. Dead code (`TERRAIN_POWER_MULTIPLIERS`, test-only `aggregate_to_display_segments`) is deleted in Phase A. The `headwind_mps` kwarg crash is fixed here as a bug tier. `scripts/calibrate_pacing_model.py` consumes `pacing_model` for defaults/coefficients so the validation harness validates the shipped formula. Verification: golden output pins (exact plan outputs for flat/rolling/HC/descent courses × default and calibrated coefficients) plus `GenerateRacePlan` end-to-end with fakes, captured before any code moves.

**Phase B — physics unification (behavior change), gated on Phase A pins being green.**
- **B1 Curvature:** one Menger curvature definition (1/m) shared by runtime and calibration; cornering speed limit `v = min(v_physics, √(a_lat/κ))` replaces the threshold tables and multiplicative factor; `descent_aggressiveness` maps to lateral acceleration `a_lat`; grade-only physics fallback for elevation profiles without lat/lon.
- **B2 Braking envelope:** look-ahead cap `d_brake = (v² − v_corner²) / (2·a_brake)` so speed can actually be shed before a corner; makes the fine-grained loop stateful (speed depends on previous speed), so it gets its own pins. Curvature smoothing is shared with calibration to guard against GPS noise.
- **B3 Recalibration:** fit `a_lat` from corner apex speeds in the existing harness; `curvature_speed_coefficient` is retired/reinterpreted.
- **Wind:** `segment_env_params` (per-segment headwind) is wired through the fine-grained path.
- **Density:** per-point ISA air density from elevation instead of one course-wide density.

**Acceptance bar (Phase B):** mountain-course mean speed error < 10% and no single course > 25% in `calibrate_pacing_model.py`'s validation. If missed: stop and report the numbers — no silent loosening, no auto-revert.

## Consequences

- The pacing model is deep: one interface (the power model), N generators behind it. Future changes to formula, NP, or coefficients happen in one place.
- Plan outputs will change in Phase B — that is intended, not a regression, and is only accepted if the numeric bar passes.
- `curvature_speed_coefficient`'s meaning changes (old: unused runtime coefficient; new: fitted `a_lat` for cornering speed). Stored DB values need recalibration before they are meaningful.