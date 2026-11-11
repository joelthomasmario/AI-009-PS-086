"""
switching_engine.py – Inspection-severity switching logic for suppliers
and production lines.

Module Owner: Joselet K Jaison (2463030)
Team: AI-009  Section: 6BTAI

Business Rules implemented here:
  BR-04 – NORMAL ↔ TIGHTENED, TIGHTENED -> DISCONTINUED
  BR-05 – NORMAL -> REDUCED, REDUCED -> NORMAL (various triggers)
  BR-06 – DISCONTINUED: no inspection until corrective action
"""

from __future__ import annotations

from datetime import datetime
from typing import Union

from .models import (
    BatchState,
    InspectionSeverity,
    ProductionLine,
    SwitchingRecord,
    Supplier,
)

# Type alias for the two entity types that carry severity
_Source = Union[Supplier, ProductionLine]


def _source_id(source: _Source) -> str:
    if isinstance(source, Supplier):
        return source.supplier_id
    return source.line_id


def _apply_switch(
    source: _Source,
    new_severity: InspectionSeverity,
    batch_id: str,
    rule_id: str,
    event: str,
    timestamp: datetime,
) -> SwitchingRecord:
    """Apply a severity switch and append to the source's switching_history."""
    old = source.severity
    source.severity = new_severity
    record = SwitchingRecord(
        source_id=_source_id(source),
        previous_severity=old,
        new_severity=new_severity,
        triggering_batch_id=batch_id,
        rule_id=rule_id,
        event=event,
        timestamp=timestamp,
    )
    source.switching_history.append(record)
    return record


class SwitchingEngine:
    """Evaluates and applies severity switching after each inspection decision.

    Joselet K Jaison – 2463030

    Call ``process_decision`` after every batch inspection to update severity.

    Args:
        source: The Supplier or ProductionLine entity.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_discontinued(self, source: _Source) -> None:
        """Raise if severity is DISCONTINUED and no corrective action registered (BR-06).

        Raises:
            PermissionError: If the source is DISCONTINUED without corrective action.
        """
        if source.severity == InspectionSeverity.DISCONTINUED:
            if not source.corrective_action_registered:
                raise PermissionError(
                    f"Source {_source_id(source)} is DISCONTINUED (BR-06). "
                    "No inspections are permitted until a corrective action "
                    "record is registered."
                )

    def apply_corrective_action(self, source: _Source, batch_id: str, timestamp: datetime) -> SwitchingRecord:
        """Register corrective action and switch from DISCONTINUED to TIGHTENED (BR-06).

        Args:
            source: Supplier or ProductionLine in DISCONTINUED state.
            batch_id: Reference batch ID.
            timestamp: When the corrective action was registered.

        Returns:
            SwitchingRecord documenting the transition.

        Raises:
            ValueError: If source is not in DISCONTINUED state.
        """
        if source.severity != InspectionSeverity.DISCONTINUED:
            raise ValueError(
                f"Source {_source_id(source)} is not DISCONTINUED "
                f"(current: {source.severity.value}). "
                "Corrective action can only be applied to DISCONTINUED sources (BR-06)."
            )
        source.corrective_action_registered = True
        # Reset counters before switching to TIGHTENED
        source.consecutive_accepts = 0
        source.tightened_reject_count = 0
        source.recent_decisions = []

        return _apply_switch(
            source,
            InspectionSeverity.TIGHTENED,
            batch_id,
            "BR-06",
            "Corrective action registered; resuming at TIGHTENED",
            timestamp,
        )

    def process_decision(
        self,
        source: _Source,
        batch_id: str,
        accepted: bool,
        is_late: bool,
        total_defects: int,
        reduced_ac: int,
        between_ac_and_re: bool,
        inspection_timestamp: datetime,
    ) -> list[SwitchingRecord]:
        """Evaluate all switching rules and apply any triggered transition.

        Joselet K Jaison – 2463030

        Args:
            source: Supplier or ProductionLine.
            batch_id: Batch just inspected.
            accepted: Whether the batch was accepted.
            is_late: True if result was recorded late (BR-11; LATE results
                     must not count toward NORMAL->REDUCED).
            total_defects: Total defect count across all classes (for BR-04
                           NORMAL->REDUCED defect limit check).
            reduced_ac: The REDUCED inspection's Ac value used for the
                        total-defects limit check (BR-04).
            between_ac_and_re: True if REDUCED result fell between Ac and Re (BR-05).
            inspection_timestamp: Timestamp of the inspection.

        Returns:
            List of SwitchingRecord objects created during this call.
        """
        records: list[SwitchingRecord] = []
        sev = source.severity

        # --- Update sliding window (last 5 decisions) ---
        source.recent_decisions.append(accepted)
        if len(source.recent_decisions) > 5:
            source.recent_decisions.pop(0)

        # --- Check production irregularity for REDUCED (BR-05) ---
        if sev == InspectionSeverity.REDUCED and source.last_inspection_at is not None:
            gap_days = (inspection_timestamp - source.last_inspection_at).total_seconds() / 86400.0
            if gap_days > 30:
                source.consecutive_accepts = 0
                r = _apply_switch(
                    source,
                    InspectionSeverity.NORMAL,
                    batch_id,
                    "BR-05",
                    f"Production irregularity: gap={gap_days:.1f} days > 30 days",
                    inspection_timestamp,
                )
                records.append(r)
                sev = source.severity

        # Update last inspection timestamp
        source.last_inspection_at = inspection_timestamp

        if sev == InspectionSeverity.NORMAL:
            records.extend(
                self._process_normal(
                    source, batch_id, accepted, is_late,
                    total_defects, reduced_ac, inspection_timestamp
                )
            )

        elif sev == InspectionSeverity.TIGHTENED:
            records.extend(
                self._process_tightened(source, batch_id, accepted, inspection_timestamp)
            )

        elif sev == InspectionSeverity.REDUCED:
            records.extend(
                self._process_reduced(
                    source, batch_id, accepted, between_ac_and_re, inspection_timestamp
                )
            )

        # DISCONTINUED: check_discontinued() must be called before inspection starts;
        # no switching logic needed here (the source stays DISCONTINUED until
        # corrective action via apply_corrective_action()).

        return records

    # ------------------------------------------------------------------
    # Per-severity processing  (Joselet K Jaison – 2463030)
    # ------------------------------------------------------------------

    def _process_normal(
        self,
        source: _Source,
        batch_id: str,
        accepted: bool,
        is_late: bool,
        total_defects: int,
        reduced_ac: int,
        timestamp: datetime,
    ) -> list[SwitchingRecord]:
        records: list[SwitchingRecord] = []

        if accepted:
            # Only non-late results count toward NORMAL->REDUCED (BR-11)
            if not is_late:
                source.consecutive_accepts += 1
            # BR-04: NORMAL -> REDUCED requires 10 consecutive acceptances AND
            # total defects within the reduced-limit column (Ac of REDUCED plan)
            if source.consecutive_accepts >= 10 and total_defects <= reduced_ac:
                source.consecutive_accepts = 0
                r = _apply_switch(
                    source,
                    InspectionSeverity.REDUCED,
                    batch_id,
                    "BR-04",
                    "10 consecutive acceptances; defects within REDUCED limit",
                    timestamp,
                )
                records.append(r)
        else:
            source.consecutive_accepts = 0
            # BR-04: NORMAL -> TIGHTENED if 2+ rejections in last 5 batches
            reject_count = source.recent_decisions.count(False)
            if reject_count >= 2:
                source.tightened_reject_count = 0  # reset cumulative tightened counter
                r = _apply_switch(
                    source,
                    InspectionSeverity.TIGHTENED,
                    batch_id,
                    "BR-04",
                    f"{reject_count} rejections in last {len(source.recent_decisions)} batches",
                    timestamp,
                )
                records.append(r)

        return records

    def _process_tightened(
        self,
        source: _Source,
        batch_id: str,
        accepted: bool,
        timestamp: datetime,
    ) -> list[SwitchingRecord]:
        records: list[SwitchingRecord] = []

        if accepted:
            source.consecutive_accepts += 1
            # BR-04: TIGHTENED -> NORMAL after 5 consecutive acceptances
            if source.consecutive_accepts >= 5:
                source.consecutive_accepts = 0
                source.tightened_reject_count = 0
                r = _apply_switch(
                    source,
                    InspectionSeverity.NORMAL,
                    batch_id,
                    "BR-04",
                    "5 consecutive acceptances while TIGHTENED",
                    timestamp,
                )
                records.append(r)
        else:
            source.consecutive_accepts = 0
            source.tightened_reject_count += 1
            # BR-04: TIGHTENED -> DISCONTINUED after 5 cumulative rejections
            if source.tightened_reject_count >= 5:
                r = _apply_switch(
                    source,
                    InspectionSeverity.DISCONTINUED,
                    batch_id,
                    "BR-04",
                    f"5 cumulative rejections while TIGHTENED (total={source.tightened_reject_count})",
                    timestamp,
                )
                records.append(r)

        return records

    def _process_reduced(
        self,
        source: _Source,
        batch_id: str,
        accepted: bool,
        between_ac_and_re: bool,
        timestamp: datetime,
    ) -> list[SwitchingRecord]:
        records: list[SwitchingRecord] = []

        if not accepted:
            # BR-05: Any rejection -> REDUCED -> NORMAL
            source.consecutive_accepts = 0
            r = _apply_switch(
                source,
                InspectionSeverity.NORMAL,
                batch_id,
                "BR-05",
                "Rejection during REDUCED inspection",
                timestamp,
            )
            records.append(r)
        elif between_ac_and_re:
            # BR-05: Between Ac and Re -> batch accepted, switch to NORMAL
            source.consecutive_accepts = 0
            r = _apply_switch(
                source,
                InspectionSeverity.NORMAL,
                batch_id,
                "BR-05",
                "Result between Ac and Re during REDUCED inspection (accepted, switching to NORMAL)",
                timestamp,
            )
            records.append(r)
        else:
            # Straight acceptance under REDUCED – no switching needed
            source.consecutive_accepts += 1

        return records


