#!/usr/bin/env python3
"""
Verify E2E FIT fixtures produce expected CP model values.

This script:
1. Parses each FIT file to extract power data
2. Runs peak power extraction
3. Fits the CP model to the combined data
4. Verifies CP ≈ 220W, W' ≈ 15000J

Usage:
    python scripts/verify_e2e_fit_fixtures.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend" / "src"))

from trainingdash.ingest import parse_records
from trainingdash.peaks import extract_peak_powers
from trainingdash.fitness import fit_cp_model

# Expected values
EXPECTED_CP = 220  # watts
EXPECTED_W_PRIME = 15000  # joules
TOLERANCE_CP = 5  # ±5W tolerance
TOLERANCE_W_PRIME = 1500  # ±1500J tolerance (10%)

# FIT files directory
FIT_DIR = project_root / "frontend" / "e2e" / "fixtures" / "fit-files"


def verify_fixtures():
    """Parse FIT files, extract peaks, fit CP model, and verify results."""
    
    print("=" * 60)
    print("E2E FIT Fixtures Verification")
    print("=" * 60)
    print(f"Expected: CP={EXPECTED_CP}W, W'={EXPECTED_W_PRIME}J")
    print(f"Tolerance: CP±{TOLERANCE_CP}W, W'±{TOLERANCE_W_PRIME}J")
    print()
    
    # Find CP test files
    fit_files = sorted(FIT_DIR.glob("cp-ride*.fit"))
    
    if not fit_files:
        print("ERROR: No cp-ride*.fit files found!")
        return False
    
    print(f"Found {len(fit_files)} FIT files:")
    for f in fit_files:
        print(f"  - {f.name}")
    print()
    
    # Parse each file and extract peaks
    all_peaks = []
    all_dates = []
    
    for fit_file in fit_files:
        print(f"Processing {fit_file.name}...")
        
        fit_bytes = fit_file.read_bytes()
        parsed = parse_records(fit_bytes)
        
        if "error" in parsed:
            print(f"  ERROR: {parsed['error']}")
            continue
        
        records = parsed.get("records", [])
        if not records:
            print("  ERROR: No records found")
            continue
        
        # Extract power array
        power_array = [r.get("power_w") for r in records]
        power_array = [p for p in power_array if p is not None]
        
        if not power_array:
            print("  ERROR: No power data")
            continue
        
        # Extract peak powers
        peaks = extract_peak_powers(power_array)
        
        # Get activity date from session
        session = parsed.get("session", {})
        start_ts = session.get("start_time")
        if start_ts:
            activity_date = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
        else:
            activity_date = datetime.now(timezone.utc)
        
        # Display key peaks
        print(f"  Duration: {len(power_array)}s ({len(power_array)/60:.1f} min)")
        print(f"  Key peaks:")
        for dur in [120, 180, 300, 600, 1200]:
            if dur in peaks and peaks[dur] is not None:
                print(f"    {dur//60}min ({dur}s): {peaks[dur]}W")
        
        all_peaks.append(peaks)
        all_dates.append(activity_date)
        print()
    
    if len(all_peaks) < 4:
        print(f"ERROR: Need at least 4 activities, got {len(all_peaks)}")
        return False
    
    # Fit CP model
    print("=" * 60)
    print("CP Model Fitting")
    print("=" * 60)
    
    result = fit_cp_model(all_peaks, all_dates)
    
    if result is None:
        print("ERROR: CP model fitting failed!")
        return False
    
    cp = result["cp_watts"]
    w_prime = result["w_prime_joules"]
    pp = result.get("pp_watts", 0)
    
    print(f"Results:")
    print(f"  Peak Power (PP): {pp}W")
    print(f"  Critical Power (CP): {cp}W")
    print(f"  W' (anaerobic capacity): {w_prime}J")
    print()
    
    # Verify against expected values
    cp_diff = abs(cp - EXPECTED_CP)
    w_prime_diff = abs(w_prime - EXPECTED_W_PRIME)
    
    cp_ok = cp_diff <= TOLERANCE_CP
    w_prime_ok = w_prime_diff <= TOLERANCE_W_PRIME
    
    print("Verification:")
    print(f"  CP: {cp}W (expected {EXPECTED_CP}W, diff={cp_diff}W) {'✓' if cp_ok else '✗'}")
    print(f"  W': {w_prime}J (expected {EXPECTED_W_PRIME}J, diff={w_prime_diff}J) {'✓' if w_prime_ok else '✗'}")
    print()
    
    if cp_ok and w_prime_ok:
        print("=" * 60)
        print("VERIFICATION PASSED")
        print("=" * 60)
        return True
    else:
        print("=" * 60)
        print("VERIFICATION FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = verify_fixtures()
    sys.exit(0 if success else 1)
