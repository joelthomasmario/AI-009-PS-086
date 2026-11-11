"""
hold_engine.py – ON_HOLD batch management and reinspection rules.

Module Owner: Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI

Business Rules implemented here:
  BR-08 – Hold: 30-day window, double sample size, cascade from related batch
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from .models import Batch, BatchState, DefectClass, InspectionResult

# 30-day hold window (BR-08)
_HOLD_WINDOW = timedelta(days=30)


class HoldEngine:
    """Places released batches ON_HOLD and manages reinspection rules.

    Joseph Mangaly – 2463031

    BR-08:
    - A RELEASED batch may be placed ON_HOLD within 30 days of release.
    - Trigger: a related batch (same supplier + raw-material lot) is
      subsequently rejected due to a critical defect.
    - ON_HOLD reinspection uses double the standard sample size.
    """

    def can_place_on_hold(
        self,
        batch: Batch,
        as_of: Optional[datetime] = None,
    ) -> tuple[bool, str]:
        """Check whether a released batch can be placed ON_HOLD (BR-08).

        Args:
            batch: The batch to check.
            as_of: Reference time (defaults to utcnow).

        Returns:
            (can_hold, reason)
        """
        if batch.state != BatchState.RELEASED:
            return False, f"Batch {batch.batch_id} is not RELEASED (current: {batch.state.value})."

        if batch.released_at is None:
            return False, f"Batch {batch.batch_id} has no release timestamp."

        ref = as_of or datetime.utcnow()
        days_since_release = (ref - batch.released_at).total_seconds() / 86400.0

        if days_since_release > 30:
            return (
                False,
                f"BR-08: Hold window expired. {days_since_release:.1f} days since release (> 30).",
            )

        return True, f"BR-08: Within hold window ({days_since_release:.1f} days since release)."

    def place_on_hold(
        self,
        batch: Batch,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Move a RELEASED batch to ON_HOLD (BR-08).

        Args:
            batch: The released batch.
            reason: Hold reason description.
            timestamp: Optional explicit timestamp.

        Raises:
            ValueError: If the transition is illegal.
        """
        ts = timestamp or datetime.utcnow()
        batch.transition_to(BatchState.ON_HOLD, f"ON_HOLD: {reason}", ts)

    def required_hold_sample_size(self, standard_sample_size: int) -> int:
        """Return the double sample size required for ON_HOLD reinspection (BR-08).

        Args:
            standard_sample_size: The standard sample size for this lot/severity.

        Returns:
            Twice the standard sample size.
        """
        return standard_sample_size * 2

    def find_related_released_batches(
        self,
        all_batches: List[Batch],
        source_id: str,
        raw_material_lot_id: str,
        exclude_batch_id: str,
        as_of: Optional[datetime] = None,
    ) -> List[Batch]:
        """Find all RELEASED batches from the same supplier and raw-material lot (BR-08).

        Args:
            all_batches: All batches in the system.
            source_id: Supplier or production-line ID.
            raw_material_lot_id: Raw-material lot identifier.
            exclude_batch_id: The trigger batch to exclude from results.
            as_of: Reference time for hold-window check.

        Returns:
            List of RELEASED batches eligible for ON_HOLD placement.
        """
        ref = as_of or datetime.utcnow()
        return [
            b for b in all_batches
            if b.batch_id != exclude_batch_id
            and b.source_id == source_id
            and b.raw_material_lot_id == raw_material_lot_id
            and b.state == BatchState.RELEASED
            and b.released_at is not None
            and (ref - b.released_at).total_seconds() / 86400.0 <= 30
        ]

