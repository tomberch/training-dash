#!/usr/bin/env python3
"""
Generate E2E test FIT fixtures for CP model verification.

Target values: CP=220W, W'=15000J
Formula: P(t) = CP + W'/t

This script generates 5 FIT files with specific power profiles that,
when analyzed together, should produce CP ≈ 220W.

Usage:
    python scripts/generate_e2e_fit_fixtures.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "tests"))

from fixtures.generate_fit import make_test_fit_with_profile

# Target CP model values
CP = 220  # watts
W_PRIME = 15000  # joules

# Output directory
OUTPUT_DIR = project_root / "frontend" / "e2e" / "fixtures" / "fit-files"


def target_power(duration_s: int) -> int:
    """Calculate target power for given duration using P(t) = CP + W'/t"""
    return int(round(CP + W_PRIME / duration_s))


def generate_ride1_2min_effort() -> bytes:
    """
    Ride 1: 2-minute all-out effort
    Peak power at 120s = 345W (220 + 15000/120)
    """
    intervals = [
        (300, 120),   # 5 min warmup at 120W
        (120, 345),   # 2 min ALL-OUT effort at 345W (key data point)
        (300, 100),   # 5 min cooldown at 100W
    ]
    return make_test_fit_with_profile(
        intervals,
        start_time=datetime(2026, 7, 1, 9, 0, 0, tzinfo=timezone.utc),
    )


def generate_ride2_5min_effort() -> bytes:
    """
    Ride 2: 5-minute threshold effort
    Peak power at 300s = 270W (220 + 15000/300)
    """
    intervals = [
        (300, 130),   # 5 min warmup at 130W
        (300, 270),   # 5 min effort at 270W (key data point)
        (300, 110),   # 5 min cooldown at 110W
    ]
    return make_test_fit_with_profile(
        intervals,
        start_time=datetime(2026, 7, 5, 9, 0, 0, tzinfo=timezone.utc),
    )


def generate_ride3_10min_effort() -> bytes:
    """
    Ride 3: 10-minute tempo effort
    Peak power at 600s = 245W (220 + 15000/600)
    """
    intervals = [
        (300, 130),   # 5 min warmup at 130W
        (600, 245),   # 10 min effort at 245W (key data point)
        (300, 100),   # 5 min cooldown at 100W
    ]
    return make_test_fit_with_profile(
        intervals,
        start_time=datetime(2026, 7, 10, 9, 0, 0, tzinfo=timezone.utc),
    )


def generate_ride4_20min_effort() -> bytes:
    """
    Ride 4: 20-minute FTP-style effort
    Peak power at 1200s = 232.5W ≈ 233W (220 + 15000/1200)
    
    Note: 20-min is outside the 2-12min fitting range but provides
    context for the CP model and tests the auto-threshold trigger.
    """
    intervals = [
        (300, 130),   # 5 min warmup at 130W
        (1200, 233),  # 20 min effort at 233W (rounded from 232.5)
        (300, 100),   # 5 min cooldown at 100W
    ]
    return make_test_fit_with_profile(
        intervals,
        start_time=datetime(2026, 7, 15, 9, 0, 0, tzinfo=timezone.utc),
    )


def generate_ride5_mixed() -> bytes:
    """
    Ride 5: Long ride with mixed efforts
    Includes multiple intensities to simulate a real training ride.
    Has a 3-min effort at ~285W to add another data point.
    """
    # P(180s) = 220 + 15000/180 = 303W
    intervals = [
        (600, 120),   # 10 min easy warmup
        (180, 303),   # 3 min hard effort at 303W
        (300, 100),   # 5 min recovery
        (600, 180),   # 10 min tempo at 180W
        (300, 100),   # 5 min recovery
        (120, 250),   # 2 min moderate effort (below 345W peak)
        (600, 150),   # 10 min endurance
        (300, 100),   # 5 min cooldown
    ]
    return make_test_fit_with_profile(
        intervals,
        start_time=datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc),
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Generating E2E FIT fixtures for CP model verification")
    print(f"Target: CP={CP}W, W'={W_PRIME}J")
    print(f"Output: {OUTPUT_DIR}")
    print()
    
    # Calculate and display expected powers
    print("Expected peak powers (P = CP + W'/t):")
    for dur, name in [(120, "2min"), (180, "3min"), (300, "5min"), (600, "10min"), (1200, "20min")]:
        print(f"  {name}: {target_power(dur)}W")
    print()
    
    # Generate files
    files = [
        ("cp-ride1-2min.fit", generate_ride1_2min_effort, "2-min effort @ 345W"),
        ("cp-ride2-5min.fit", generate_ride2_5min_effort, "5-min effort @ 270W"),
        ("cp-ride3-10min.fit", generate_ride3_10min_effort, "10-min effort @ 245W"),
        ("cp-ride4-20min.fit", generate_ride4_20min_effort, "20-min effort @ 233W"),
        ("cp-ride5-mixed.fit", generate_ride5_mixed, "Mixed efforts with 3-min @ 303W"),
    ]
    
    for filename, generator, description in files:
        fit_bytes = generator()
        output_path = OUTPUT_DIR / filename
        output_path.write_bytes(fit_bytes)
        print(f"✓ {filename} ({len(fit_bytes):,} bytes) - {description}")
    
    # Also create a simple test-ride.fit for basic upload tests
    simple_ride = make_test_fit_with_profile(
        [(600, 180), (300, 220), (600, 160)],  # 25 min ride
        start_time=datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
    )
    simple_path = OUTPUT_DIR / "test-ride.fit"
    simple_path.write_bytes(simple_ride)
    print(f"✓ test-ride.fit ({len(simple_ride):,} bytes) - Simple test ride for upload tests")
    
    print()
    print("Done! Files ready for E2E tests.")


if __name__ == "__main__":
    main()
