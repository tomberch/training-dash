#!/usr/bin/env python3
"""Debug script to check timer vs elapsed time in FIT files."""

import sys

from garmin_fit_sdk import Decoder, Stream


def check_fit_file(filepath: str):
    """Check timer time vs elapsed time in a FIT file."""
    print(f"\nChecking: {filepath}")
    print("-" * 60)

    stream = Stream.from_file(filepath)
    decoder = Decoder(stream)
    messages, errors = decoder.read()

    if errors:
        print(f"Decode errors: {errors}")

    for session in messages.get("session_mesgs", []):
        print("\nSession message fields:")
        for key, value in session.items():
            if "time" in key.lower() or "timer" in key.lower():
                print(f"  {key}: {value}")

        # Specifically check our fields
        timer = session.get("total_timer_time")
        elapsed = session.get("total_elapsed_time")

        print(f"\n  total_timer_time (moving):  {timer}")
        print(f"  total_elapsed_time (total): {elapsed}")
        if timer and elapsed:
            diff = elapsed - timer
            print(f"  Difference (stopped time):  {diff:.1f}s ({diff / 60:.1f}min)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_fit_times.py <fit_file>")
        sys.exit(1)

    check_fit_file(sys.argv[1])
