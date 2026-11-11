"""
recall_engine.py – Batch recall and cascade recall logic.

Module Owner: Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI

Business Rules implemented here:
  BR-09 – Recall triggers and cascade to batches sharing same raw-material lot
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import uuid

from .models import Batch, BatchState, DefectClass, InspectionResult, RecallRecord


class RecallEngine:
    """Initiates and cascades recalls across batches sharing a raw-material lot.

    Joseph Mangaly – 2463031

    BR-09:
    - Trigger 1: Critical defect found during ON_HOLD reinspection.
    - Trigger 2: Customer complaint cites the batch.
    - Cascade: All non-expired batches sharing the same raw-material lot
      that have not already reached a terminal state (RECALLED) are recalled.
    - Expired batches are excluded from the cascade.
    """

    def recall_batch(
        self,
        trigger_batch: Batch,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Move one batch to RECALLED (terminal state).

        Args:
            trigger_batch: The batch being recalled.
            reason: Human-readable recall reason.
            timestamp: Optional explicit timestamp.

        Raises:
            ValueError: If the transition is illegal.
        """
        ts = timestamp or datetime.utcnow()
        trigger_batch.transition_to(BatchState.RECALLED, f"RECALLED: {reason}", ts)

    def cascade_recall(
        self,
        all_batches: List[Batch],
        trigger_batch_id: str,
        raw_material_lot_id: str,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> RecallRecord:
        """Cascade a recall to all non-expired batches sharing the raw-material lot (BR-09).

        Args:
            all_batches: All batches in the system.
            trigger_batch_id: The batch that triggered the recall.
            raw_material_lot_id: Common raw-material lot identifier.
            reason: Human-readable recall reason.
            timestamp: Optional explicit timestamp.

        Returns:
            RecallRecord documenting the event and all recalled batch IDs.
        """
        ts = timestamp or datetime.utcnow()
        recalled_ids: List[str] = []

        for batch in all_batches:
            if batch.raw_material_lot_id != raw_material_lot_id:
                continue

            # Skip already-terminal batches
            if batch.state == BatchState.RECALLED:
                recalled_ids.append(batch.batch_id)  # already counted
                continue

            # BR-09: Skip expired batches
            if batch.expiry_date is not None and batch.expiry_date <= ts:
                # Expired batches are excluded from cascade
                continue

            # Only recall batches that have not been permanently disposed
            if batch.state != BatchState.RECALLED:
                try:
                    batch.transition_to(BatchState.RECALLED, f"CASCADE RECALL: {reason}", ts)
                    recalled_ids.append(batch.batch_id)
                except ValueError:
                    # Batch in a state that cannot be recalled (e.g. already RECALLED)
                    pass

        return RecallRecord(
            recall_id=str(uuid.uuid4()),
            trigger_batch_id=trigger_batch_id,
            recalled_batch_ids=recalled_ids,
            reason=reason,
            rule_id="BR-09",
            recalled_at=ts,
        )

    def check_on_hold_critical(self, result: InspectionResult) -> bool:
        """Return True if the ON_HOLD reinspection found a critical defect (BR-09).

        Args:
            result: Inspection result from ON_HOLD reinspection.

        Returns:
            True if critical defects > 0.
        """
        return result.defects_for(DefectClass.CRITICAL) > 0

