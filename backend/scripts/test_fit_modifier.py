#!/usr/bin/env python3
"""Test FIT modifier by extracting and modifying an activity's FIT file."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trainingdash.domain.fit_modifier import FitModifications, modify_fit


async def main():
    # Read original FIT from stdin or file
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        original_fit = input_path.read_bytes()
        print(f"Read {len(original_fit)} bytes from {input_path}", file=sys.stderr)
    else:
        print("Usage: python test_fit_modifier.py <input.fit> [output.fit]", file=sys.stderr)
        print("       Will modify to Edge 840 (product_id=4062)", file=sys.stderr)
        sys.exit(1)

    # Apply modifications (Edge 840 = 4062)
    modifications = FitModifications(device_product_id=4062)

    try:
        modified_fit = modify_fit(original_fit, modifications)
        print(f"Modified FIT: {len(modified_fit)} bytes", file=sys.stderr)

        # Write output
        if len(sys.argv) > 2:
            output_path = Path(sys.argv[2])
            output_path.write_bytes(modified_fit)
            print(f"Written to {output_path}", file=sys.stderr)
        else:
            # Write to stdout
            sys.stdout.buffer.write(modified_fit)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
