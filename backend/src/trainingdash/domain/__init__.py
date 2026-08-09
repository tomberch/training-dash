"""
Domain layer — pure business logic with no I/O dependencies.

This package contains computation modules that work with plain data types
(numbers, sequences, dictionaries) and have no database, network, or
filesystem dependencies. They are easy to unit test and reason about.

Modules:
- fitness: TSS, NP, IF calculations and Critical Power model
- pmc: Performance Management Chart (CTL/ATL/TSB)
- peaks: Peak power detection for power curves
- wbal: W'bal (W-prime balance) computation
- zones: HR and power zone calculations
- metrics: Activity metrics computation
- polyline: Google polyline encoding for map thumbnails
- resampler: Time-series resampling by distance
"""
