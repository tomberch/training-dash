"""
Repository protocols — abstract interfaces for data access.

These protocols define the contract that repository implementations must fulfill.
Use cases depend on these protocols, not on concrete implementations,
enabling testing with in-memory fakes.

Concrete implementations:
- postgres/: PostgreSQL implementations using SQLAlchemy
- tests/fakes/: In-memory fakes for unit testing
"""

from typing import Protocol

# Repository protocols will be added in subsequent tickets:
# - #263: ActivityRepo
# - #264: UserRepo
# - #265: RouteRepo, CredentialsRepo, AuditLogRepo, etc.
