"""
inspection_engine.py – Orchestrates the full inspection pipeline for a batch.

Integrates: sampling_engine, switching_engine, lifecycle_engine,
            rework_engine, hold_engine, recall_engine.

Shared module (all team members)
Team: AI-009  Section: 6BTAI

Business Rules coordinated here:
  BR-01 through BR-11 (via the respective engines)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

from .models import (
    Batch,
    BatchDecision,
    BatchState,
    CorrectiveAction,
    CustomerComplaint,
    DecisionCode,
    DefectClass,
    DefectClassConfig,
    InspectionResult,
    InspectionSeverity,
    ProductionLine,
    RecallRecord,
    Supplier,
)
from .sampling_engine import SamplingDecision, SamplingEngine, SamplingPlanLoader
from .switching_engine import SwitchingEngine
from .lifecycle_engine import LifecycleEngine
from .rework_engine import ReworkEngine
from .hold_engine import HoldEngine
from .recall_engine import RecallEngine

_LATE_THRESHOLD = timedelta(hours=48)
_MIN_SHELF_LIFE_RATIO = 0.75


class InspectionEngine:
    """Central orchestrator for the AQL inspection pipeline.

    This class coordinates all engines to process a single batch
    through its inspection lifecycle.

    Shared ownership – AI-009
    """

    def __init__(self, plan_loader: SamplingPlanLoader) -> None:
        self._sampler = SamplingEngine(plan_loader)
        self._switcher = SwitchingEngine()
        self._lifecycle = LifecycleEngine()
        self._rework = ReworkEngine()
        self._hold = HoldEngine()
        self._recall = RecallEngine()

    # ------------------------------------------------------------------
    # Step 1: Begin inspection
    # ------------------------------------------------------------------

    def begin_inspection(
        self,
        batch: Batch,
        source: Union[Supplier, ProductionLine],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Move batch from QUARANTINE to UNDER_INSPECTION.

        Checks for DISCONTINUED status before allowing inspection.

        Args:
            batch: Batch to begin inspecting.
            source: Associated Supplier or ProductionLine.
            timestamp: Optional explicit timestamp.

        Raises:
            PermissionError: If source is DISCONTINUED without corrective action (BR-06).
            ValueError: If the batch state transition is illegal.
        """
        self._switcher.check_discontinued(source)
        self._lifecycle.begin_inspection(batch, timestamp)

    # ------------------------------------------------------------------
    # Step 2: Record and evaluate inspection result
    # ------------------------------------------------------------------

    def record_result(
        self,
        batch: Batch,
        source: Union[Supplier, ProductionLine],
        defect_configs: List[DefectClassConfig],
        defects: Dict[DefectClass, int],
        sampled_at: datetime,
        recorded_at: Optional[datetime] = None,
        rework_round: int = 0,
    ) -> Tuple[BatchDecision, List]:
        """Record an inspection result and produce a BatchDecision.

        Args:
            batch: Batch being inspected (must be UNDER_INSPECTION).
            source: Supplier or ProductionLine.
            defect_configs: Defect-class AQL configuration.
            defects: Observed defect counts by class.
            sampled_at: When sampling was performed.
            recorded_at: When the result was entered (defaults to utcnow).
            rework_round: 0 for original, 1 for rework reinspection.

        Returns:
            (BatchDecision, list_of_SwitchingRecords)

        Raises:
            ValueError: If batch is not UNDER_INSPECTION.
        """
        if batch.state != BatchState.UNDER_INSPECTION:
            raise ValueError(
                f"Batch {batch.batch_id} must be UNDER_INSPECTION to record a result "
                f"(current: {batch.state.value})."
            )

        rec_at = recorded_at or datetime.utcnow()
        severity = source.severity

        # For rework reinspection, severity is TIGHTENED (BR-07)
        if rework_round > 0:
            severity = InspectionSeverity.TIGHTENED

        # Build InspectionResult
        result = InspectionResult(
            batch_id=batch.batch_id,
            sample_size=0,  # will be set below
            defects=defects,
            sampled_at=sampled_at,
            recorded_at=rec_at,
            rework_round=rework_round,
        )

        # BR-11: Mark late
        self._lifecycle.mark_late(result)

        # Determine sample size (BR-01, BR-03)
        major_aql = self._get_major_aql(defect_configs)
        sample_size, code_letter, is_100pct = self._sampler.required_sample_size(
            batch.lot_size, major_aql, severity
        )

        # BR-08: ON_HOLD reinspection — capture flag before reset, then double sample size
        hold_active = batch.hold_reinspection
        if hold_active:
            doubled = sample_size * 2
            result.sample_size = min(doubled, batch.lot_size)
            batch.hold_reinspection = False  # reset flag after capturing
        else:
            result.sample_size = batch.lot_size if is_100pct else sample_size

        # Evaluate against sampling plan (BR-01, BR-02, BR-03)
        if severity == InspectionSeverity.REDUCED:
            sampling_decision, between_ac_re = self._sampler.evaluate_reduced_between(
                batch.batch_id, batch.lot_size, defect_configs, result, severity
            )
        else:
            sampling_decision = self._sampler.evaluate(
                batch.batch_id, batch.lot_size, defect_configs, result, severity
            )
            between_ac_re = False

        batch.inspection_results.append(result)

        # Build per-class Ac/Re dicts for the BatchDecision record
        ac_values: Dict[DefectClass, int] = {}
        re_values: Dict[DefectClass, int] = {}
        for ev in sampling_decision.per_class:
            ac_values[ev.defect_class] = ev.ac
            re_values[ev.defect_class] = ev.re

        # Determine MAJOR Re for rework eligibility check later
        major_re = re_values.get(DefectClass.MAJOR, 0)

        # Build decision code and reason
        decision_code = sampling_decision.decision_code
        decision_reason = sampling_decision.decision_reason
        rule_ids = sampling_decision.rule_ids[:]

        # BR-08: tag ON_HOLD reinspection decisions
        if hold_active and "BR-08" not in rule_ids:
            rule_ids.append("BR-08")

        # BR-05: between-Ac-and-Re under REDUCED
        if between_ac_re and sampling_decision.overall_accepted:
            decision_code = DecisionCode.ACCEPTED_SWITCH_TO_NORMAL
            decision_reason += "; Result between Ac and Re under REDUCED – accepted, switching to NORMAL (BR-05)"
            rule_ids.append("BR-05")

        # BR-11: mark late
        if result.is_late:
            decision_reason += " [LATE RESULT – BR-11]"
            rule_ids.append("BR-11")

        # Switching engine (BR-04, BR-05, BR-06) – Joselet K Jaison
        # Compute reduced_ac for the total-defects limit check
        reduced_ac = self._get_reduced_ac(batch.lot_size, defect_configs)
        total_defects = result.total_defects()

        switching_records = self._switcher.process_decision(
            source=source,
            batch_id=batch.batch_id,
            accepted=sampling_decision.overall_accepted,
            is_late=result.is_late,
            total_defects=total_defects,
            reduced_ac=reduced_ac,
            between_ac_and_re=between_ac_re,
            inspection_timestamp=sampled_at,
        )

        batch_decision = BatchDecision(
            batch_id=batch.batch_id,
            product_id=batch.product_id,
            source_id=batch.source_id,
            lot_size=batch.lot_size,
            code_letter=code_letter,
            severity=severity,
            sample_size=result.sample_size,
            defects=defects,
            ac_values=ac_values,
            re_values=re_values,
            decision=decision_code,
            decision_reason=decision_reason,
            rule_ids=rule_ids,
            sampled_at=sampled_at,
            recorded_at=rec_at,
            is_late=result.is_late,
        )

        return batch_decision, switching_records

    # ------------------------------------------------------------------
    # Step 3: Release / reject after evaluation
    # ------------------------------------------------------------------

    def apply_decision(
        self,
        batch: Batch,
        batch_decision: BatchDecision,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Apply the BatchDecision to the batch's lifecycle state.

        Args:
            batch: The batch under inspection.
            batch_decision: Decision produced by record_result.
            timestamp: Optional explicit timestamp.

        Raises:
            ValueError: If the state transition is illegal.
        """
        ts = timestamp or datetime.utcnow()
        accepted = batch_decision.decision in (
            DecisionCode.ACCEPTED,
            DecisionCode.ACCEPTED_SWITCH_TO_NORMAL,
        )

        if accepted:
            # Try to release, enforcing shelf-life (BR-10)
            success, _, _ = self._lifecycle.try_release(batch, ts)
            if not success:
                # Already moved to REJECTED with reason SHORT_DATED
                pass
        else:
            reason = batch_decision.decision.value + ": " + batch_decision.decision_reason
            self._lifecycle.reject_batch(batch, reason, ts)

    # ------------------------------------------------------------------
    # Rework (BR-07)
    # ------------------------------------------------------------------

    def begin_rework(
        self,
        batch: Batch,
        major_re: int,
        timestamp: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """Attempt to begin rework on a rejected batch.

        Args:
            batch: The batch in REJECTED state.
            major_re: Re value for MAJOR defects (from the last sampling plan lookup).
            timestamp: Optional explicit timestamp.

        Returns:
            (success, reason)
        """
        last = batch.latest_result
        if last is None:
            return False, "No inspection result found for batch."

        eligible, reason = self._rework.is_eligible(batch, last, major_re)
        if not eligible:
            return False, reason

        self._rework.begin_rework(batch, timestamp)
        return True, reason

    def begin_hold_inspection(
        self,
        batch: Batch,
        source: Union[Supplier, ProductionLine],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Move ON_HOLD batch to UNDER_INSPECTION for reinspection (BR-08).

        Checks DISCONTINUED status before allowing inspection.
        Sets batch.hold_reinspection = True (double sample size flag).

        Args:
            batch: The ON_HOLD batch to reinspect.
            source: Associated Supplier or ProductionLine.
            timestamp: Optional explicit timestamp.

        Raises:
            PermissionError: If source is DISCONTINUED without corrective action (BR-06).
            ValueError: If the batch state transition is illegal.
        """
        self._switcher.check_discontinued(source)
        self._lifecycle.begin_hold_inspection(batch, timestamp)

    def begin_reinspection(self, batch: Batch, timestamp: Optional[datetime] = None) -> None:
        """Move REWORK batch to UNDER_INSPECTION for reinspection (BR-07)."""
        self._rework.begin_reinspection(batch, timestamp)

    # ------------------------------------------------------------------
    # Hold (BR-08)
    # ------------------------------------------------------------------

    def place_on_hold(
        self,
        batch: Batch,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """Place a released batch ON_HOLD (BR-08).

        Args:
            batch: The released batch.
            reason: Hold reason.
            timestamp: Optional explicit timestamp.

        Returns:
            (success, message)
        """
        ts = timestamp or datetime.utcnow()
        can, msg = self._hold.can_place_on_hold(batch, ts)
        if not can:
            return False, msg
        self._hold.place_on_hold(batch, reason, ts)
        return True, msg

    def find_related_for_hold(
        self,
        all_batches: List[Batch],
        source_id: str,
        raw_material_lot_id: str,
        exclude_batch_id: str,
        timestamp: Optional[datetime] = None,
    ) -> List[Batch]:
        """Find all RELEASED batches eligible for hold cascade (BR-08)."""
        return self._hold.find_related_released_batches(
            all_batches, source_id, raw_material_lot_id, exclude_batch_id, timestamp
        )

    def hold_sample_size(self, standard_n: int) -> int:
        """Return double sample size for ON_HOLD reinspection (BR-08)."""
        return self._hold.required_hold_sample_size(standard_n)

    # ------------------------------------------------------------------
    # Recall (BR-09)
    # ------------------------------------------------------------------

    def trigger_recall(
        self,
        all_batches: List[Batch],
        trigger_batch: Batch,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> RecallRecord:
        """Trigger and cascade a recall (BR-09).

        Args:
            all_batches: All batches in the system.
            trigger_batch: The batch triggering the recall.
            reason: Human-readable recall reason.
            timestamp: Optional explicit timestamp.

        Returns:
            RecallRecord documenting all recalled batches.
        """
        ts = timestamp or datetime.utcnow()
        return self._recall.cascade_recall(
            all_batches=all_batches,
            trigger_batch_id=trigger_batch.batch_id,
            raw_material_lot_id=trigger_batch.raw_material_lot_id,
            reason=reason,
            timestamp=ts,
        )

    def check_on_hold_critical(self, result: InspectionResult) -> bool:
        """Return True if critical defects found during ON_HOLD reinspection (BR-09)."""
        return self._recall.check_on_hold_critical(result)

    # ------------------------------------------------------------------
    # Corrective action (BR-06)
    # ------------------------------------------------------------------

    def register_corrective_action(
        self,
        source: Union[Supplier, ProductionLine],
        action: CorrectiveAction,
    ) -> None:
        """Register a corrective action and switch to TIGHTENED (BR-06).

        Args:
            source: The DISCONTINUED Supplier or ProductionLine.
            action: The corrective action record.

        Raises:
            ValueError: If source is not DISCONTINUED.
        """
        self._switcher.apply_corrective_action(source, action.action_id, action.registered_at)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_major_aql(defect_configs: List[DefectClassConfig]) -> float:
        for dc in defect_configs:
            if dc.defect_class == DefectClass.MAJOR:
                return dc.aql
        return 1.0

    def _get_reduced_ac(
        self, lot_size: int, defect_configs: List[DefectClassConfig]
    ) -> int:
        """Get the Ac value from the REDUCED plan (used for NORMAL->REDUCED check)."""
        try:
            from .sampling_engine import get_code_letter
            code = get_code_letter(lot_size)
            major_aql = self._get_major_aql(defect_configs)
            entry = self._sampler._loader.lookup(code, major_aql, InspectionSeverity.REDUCED)
            return entry.ac
        except (KeyError, ValueError):
            # If REDUCED plan not available, use a large number (effectively no limit)
            return 999999


