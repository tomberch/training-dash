"""Shared test fixtures and cached values for integration tests."""

from trainingdash.auth import hash_password

# Pre-compute password hashes once (bcrypt is intentionally slow, ~0.2s per hash)
CACHED_HASH_TESTPASS = hash_password("testpass")
CACHED_HASH_PASS = hash_password("pass")
