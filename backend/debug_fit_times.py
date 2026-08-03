#!/usr/bin/env python3
"""Debug script to check timer vs elapsed time in FIT files."""

import sys
import fitdecode

def check_fit_file(filepath: str):
    """Check timer time vs elapsed time in a FIT file."""
    print(f"\nChecking: {filepath}")
    print("-" * 60)
    
    with fitdecode.FitReader(filepath) as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.FitDataMessage):
                if frame.name == "session":
                    print(f"\nSession frame fields:")
                    for field in frame.fields:
                        if "time" in field.name.lower() or "timer" in field.name.lower():
                            print(f"  {field.name}: {field.value}")
                    
                    # Specifically check our fields
                    timer = None
                    elapsed = None
                    for field in frame.fields:
                        if field.name == "total_timer_time":
                            timer = field.value
                        elif field.name == "total_elapsed_time":
                            elapsed = field.value
                    
                    print(f"\n  total_timer_time (moving):  {timer}")
                    print(f"  total_elapsed_time (total): {elapsed}")
                    if timer and elapsed:
                        diff = elapsed - timer
                        print(f"  Difference (stopped time):  {diff:.1f}s ({diff/60:.1f}min)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_fit_times.py <fit_file>")
        sys.exit(1)
    
    check_fit_file(sys.argv[1])
