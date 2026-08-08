"""
Repository layer — data access abstractions.

This package contains:
- protocols.py: Abstract interfaces (Protocols) for repositories
- postgres/: PostgreSQL implementations of the repository protocols

The protocols allow use cases to depend on abstractions rather than
concrete database implementations, enabling testing with in-memory fakes.
"""
