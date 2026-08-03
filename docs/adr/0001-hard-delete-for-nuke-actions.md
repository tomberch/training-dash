# ADR 0001: Hard Delete for Nuke Actions

## Status

Accepted

## Context

The admin panel needs a "Nuke Button" to delete user data (activities, integrations, or entire accounts). We considered three approaches for handling deleted data:

1. **Hard delete** — data is permanently removed from the database
2. **Soft delete** — data is marked with `deleted_at` timestamp, hidden from UI, purged after N days
3. **Archive** — data is exported to a file or archive table before deletion

## Decision

We will use **hard delete** for all nuke actions.

Safety is provided by:
- A count preview showing exactly what will be deleted
- Type-to-confirm requiring the admin to enter the target user's email
- An audit log recording metadata about each nuke action (who, what, when)

## Consequences

**Benefits:**
- Simple implementation — no `WHERE deleted_at IS NULL` filters throughout the codebase
- No storage cost for "deleted" data
- No purge job to maintain
- No restore UI to build

**Drawbacks:**
- No undo capability — if the safety mechanism fails, data is gone
- Recovery requires restoring from database backup

**Mitigations:**
- The type-to-confirm mechanism makes accidental deletion unlikely
- Database backups provide a recovery path for genuine mistakes
- Audit log provides visibility into what was deleted and when

This is appropriate for a small family app where nuke actions are rare and the admin (the developer) can restore from backup if needed.
