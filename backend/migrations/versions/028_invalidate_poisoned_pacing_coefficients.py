"""Invalidate grade-power coefficients fitted with the poisoned normalizer.

The pre-ADR-0005 climb fitter normalized power by whole-ride average
(including 0W coasting), producing inflated intercepts and crushed slopes
(reference rider: intercept 1.30, slope 0.02, R² 0.009). Coefficients fitted
with that normalizer cannot be trusted; plans must fall back to defaults
until a recalibration under the fixed pipeline lands.

Realize the invalidation by zeroing activity_count (the runtime treats
activity_count == 0 as "not calibrated", per effective_a_lat) and clearing
the sample counts. Rows keep their id/created_at so they can be shown as
"stale" in the API.

Revision ID: 028
Revises: 027
Create Date: 2026-08-28

"""

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE pacing_coefficients
        SET activity_count = 0,
            climb_sample_count = 0,
            descent_sample_count = 0
        """
    )


def downgrade() -> None:
    # Irrecoverable by design: the old values were produced by a broken fit.
    pass
