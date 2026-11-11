"""
rework_engine.py – Rework eligibility evaluation and rework lifecycle management.

Module Owner: Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI

Business Rules implemented here:
  BR-07 – Rework eligibility and reinspection at TIGHTENED
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import Batch, BatchState, DefectClass, InspectionResult


class ReworkEngine:
    """Evaluates rework eligibility and manages the rework lifecycle.

    Joseph Mangaly – 2463031

    BR-07 rules:
    1. A rejected batch can be reworked ONCE if:
       - Critical defects are zero.
       - Major defects <= 2 x Re(MAJOR).
    2. Reinspection uses a NEW sample at TIGHTENED severity.
    3. A second rejection is final (no further rework allowed).
    """

    def is_eligible(
        self,
        batch: Batch,
        last_result: InspectionResult,
        major_re: int,
    ) -> tuple[bool, str]:
        """Check whether a rejected batch is eligible for rework (BR-07).

        Args:
            batch: The batch in REJECTED state.
            last_result: The most recent inspection result.
            major_re: Re value for MAJOR defects at current severity.

        Returns:
            (eligible, reason) – reason explains the decision.

        Raises:
            ValueError: If the batch is not in REJECTED state.
        """
        if batch.state != BatchState.REJECTED:
            raise ValueError(
                f"Batch {batch.batch_id} is not in REJECTED state "
                f"(current: {batch.state.value})."
            )

        # BR-07: Maximum one rework
        if batch.rework_count >= 1:
            return False, "BR-07: Second rejection is final; no further rework allowed."

        critical_count = last_result.defects_for(DefectClass.CRITICAL)
        major_count = last_result.defects_for(DefectClass.MAJOR)

        if critical_count > 0:
            return (
                False,
                f"BR-07: Critical defects={critical_count} > 0; rework not permitted.",
            )

        threshold = 2 * major_re
        if major_count > threshold:
            return (
                False,
                f"BR-07: Major defects={major_count} > 2xRe={threshold}; rework not permitted.",
            )

        return True, "BR-07: Eligible for rework (critical=0, major within 2xRe)."

    def begin_rework(self, batch: Batch, timestamp: Optional[datetime] = None) -> None:
        """Transition batch from REJECTED to REWORK.

        Args:
            batch: Batch in REJECTED state.
            timestamp: Optional explicit timestamp.

        Raises:
            ValueError: If eligibility check was not performed, or transition illegal.
        """
        ts = timestamp or datetime.utcnow()
        batch.transition_to(BatchState.REWORK, "Rework started per BR-07", ts)
        batch.rework_count += 1

    def begin_reinspection(self, batch: Batch, timestamp: Optional[datetime] = None) -> None:
        """Transition batch from REWORK to UNDER_INSPECTION for reinspection (BR-07).

        Args:
            batch: Batch in REWORK state.
            timestamp: Optional explicit timestamp.
        """
        ts = timestamp or datetime.utcnow()
        batch.transition_to(
            BatchState.UNDER_INSPECTION,
            "Rework reinspection started at TIGHTENED severity (BR-07)",
            ts,
        )


