"""
lifecycle_engine.py – Batch lifecycle state management and shelf-life
validation.

Module Owner: Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI

Business Rules implemented here:
  BR-10 – Shelf life check on release
  BR-11 – 48-hour recording window (LATE flag)
  Section 6 – Legal state transitions
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .models import Batch, BatchState, DecisionCode, InspectionResult

# 48-hour threshold (BR-11): result is LATE if recorded > 48 hours after sampling
_LATE_THRESHOLD = timedelta(hours=48)

# 75% shelf-life minimum (BR-10)
_MIN_SHELF_LIFE_RATIO = 0.75


class LifecycleEngine:
    """Manages batch state transitions and enforces lifecycle rules.

    Joseph Mangaly – 2463031

    All state transitions are validated against the legal-transition map
    defined in models.LEGAL_TRANSITIONS. Illegal transitions raise ValueError.
    """

    # ------------------------------------------------------------------
    # Sampling / inspection flow
    # ------------------------------------------------------------------

    def begin_inspection(self, batch: Batch, timestamp: Optional[datetime] = None) -> None:
        """Move batch from QUARANTINE to UNDER_INSPECTION.

        Args:
            batch: The batch to transition.
            timestamp: Optional explicit timestamp (defaults to utcnow).

        Raises:
            ValueError: If the transition is illegal.
        """
        ts = timestamp or datetime.utcnow()
        batch.transition_to(BatchState.UNDER_INSPECTION, "Inspection started", ts)

    def begin_hold_inspection(self, batch: Batch, timestamp: Optional[datetime] = None) -> None:
        """Move batch from ON_HOLD to UNDER_INSPECTION for reinspection (BR-08).

        Sets batch.hold_reinspection = True to signal that InspectionEngine.record_result()
        must use double the standard sample size (capped at lot_size).

        Args:
            batch: The batch in ON_HOLD state.
            timestamp: Optional explicit timestamp (defaults to utcnow).

        Raises:
            ValueError: If the transition is illegal (batch not in ON_HOLD state).
        """
        ts = timestamp or datetime.utcnow()
        batch.hold_reinspection = True
        batch.transition_to(
            BatchState.UNDER_INSPECTION,
            "ON_HOLD reinspection started at double sample size (BR-08)",
            ts,
        )

    def mark_late(self, result: InspectionResult) -> None:
        """Flag an inspection result as LATE if recorded > 48 hours after sampling (BR-11).

        Args:
            result: The InspectionResult to evaluate.
        """
        gap = result.recorded_at - result.sampled_at
        result.is_late = gap > _LATE_THRESHOLD

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    def try_release(
        self, batch: Batch, as_of: Optional[datetime] = None
    ) -> tuple[bool, str, str]:
        """Attempt to release a batch, enforcing shelf-life check (BR-10).

        Args:
            batch: The batch to release (must be UNDER_INSPECTION or ON_HOLD).
            as_of: Reference time for shelf-life check (defaults to utcnow).

        Returns:
            (success, decision_code_str, reason)
            If success is False, the batch is moved to REJECTED with
            reason SHORT_DATED.

        Raises:
            ValueError: If the transition from current state to RELEASED is illegal.
        """
        ts = as_of or datetime.utcnow()

        # BR-10: shelf-life check
        if batch.total_shelf_life_days > 0 and batch.expiry_date is not None:
            ratio = batch.shelf_life_ratio(ts)
            if ratio is not None and ratio < _MIN_SHELF_LIFE_RATIO:
                batch.is_short_dated = True
                batch.rejection_reason = "SHORT_DATED"
                batch.transition_to(
                    BatchState.REJECTED,
                    f"SHORT_DATED: shelf-life ratio={ratio:.3f} < 0.75 (BR-10)",
                    ts,
                )
                return False, DecisionCode.REJECTED_SHORT_DATED.value, "BR-10: Remaining shelf life < 75%"

        batch.transition_to(BatchState.RELEASED, "Batch released", ts)
        return True, DecisionCode.RELEASED.value, "Shelf life OK; batch released"

    # ------------------------------------------------------------------
    # Rejection
    # ------------------------------------------------------------------

    def reject_batch(
        self, batch: Batch, reason: str, timestamp: Optional[datetime] = None
    ) -> None:
        """Move batch to REJECTED.

        Args:
            batch: The batch to reject.
            reason: Human-readable rejection reason.
            timestamp: Optional explicit timestamp.

        Raises:
            ValueError: If the transition is illegal.
        """
        ts = timestamp or datetime.utcnow()
        batch.rejection_reason = reason
        batch.transition_to(BatchState.REJECTED, reason, ts)

