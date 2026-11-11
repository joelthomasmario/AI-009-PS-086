"""
test_br08_hold.py – Tests for BR-08: Hold rules.

Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from src.hold_engine import HoldEngine
from src.lifecycle_engine import LifecycleEngine
from src.models import Batch, BatchState, DefectClass

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _released_batch(batch_id="B-REL", source_id="S001", raw_lot="RM-001", released_offset_days=0):
    b = Batch(
        batch_id=batch_id, product_id="P001",
        source_id=source_id, source_type="SUPPLIER",
        lot_size=200, raw_material_lot_id=raw_lot,
        manufacture_date=BASE,
    )
    b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)
    release_ts = BASE + timedelta(days=released_offset_days)
    b.transition_to(BatchState.RELEASED, "released", release_ts)
    # released_at is set by the transition logic
    b.released_at = release_ts
    return b


class TestHoldEligibility:
    """BR-08: Hold window and eligibility checks."""

    def test_can_hold_within_30_days(self):
        he = HoldEngine()
        b = _released_batch()
        # Released at BASE; check at BASE + 1 day
        can, reason = he.can_place_on_hold(b, as_of=BASE + timedelta(days=1))
        assert can is True

    def test_ec7_hold_exactly_30_days_allowed(self):
        """EC-7: Hold request exactly 30 days after release → allowed."""
        he = HoldEngine()
        b = _released_batch()
        exactly_30 = BASE + timedelta(days=30)
        can, reason = he.can_place_on_hold(b, as_of=exactly_30)
        assert can is True, f"Expected hold allowed at exactly 30 days, got: {reason}"

    def test_ec8_hold_31_days_after_release_rejected(self):
        """EC-8: Hold request 31 days after release → NOT allowed."""
        he = HoldEngine()
        b = _released_batch()
        day_31 = BASE + timedelta(days=31)
        can, reason = he.can_place_on_hold(b, as_of=day_31)
        assert can is False
        assert "expired" in reason.lower() or "31" in reason or "30" in reason

    def test_non_released_batch_cannot_be_held(self):
        he = HoldEngine()
        b = Batch(
            batch_id="B-Q", product_id="P001",
            source_id="S001", source_type="SUPPLIER",
            lot_size=200, raw_material_lot_id="RM-001",
            manufacture_date=BASE,
        )  # QUARANTINE state
        can, reason = he.can_place_on_hold(b)
        assert can is False
        assert "not RELEASED" in reason or "RELEASED" in reason

    def test_place_on_hold_transitions_state(self):
        he = HoldEngine()
        b = _released_batch()
        he.place_on_hold(b, "Related batch rejected", BASE + timedelta(days=5))
        assert b.state == BatchState.ON_HOLD

    def test_double_sample_size_for_hold_reinspection(self):
        he = HoldEngine()
        assert he.required_hold_sample_size(50) == 100
        assert he.required_hold_sample_size(32) == 64

    def test_find_related_released_batches(self):
        """Find RELEASED batches sharing same source and raw lot (BR-08)."""
        he = HoldEngine()
        b1 = _released_batch("B1", "S001", "RM-001")
        b2 = _released_batch("B2", "S001", "RM-001")
        b3 = _released_batch("B3", "S001", "RM-002")  # different raw lot
        b4 = _released_batch("B4", "S002", "RM-001")  # different supplier

        all_batches = [b1, b2, b3, b4]
        related = he.find_related_released_batches(
            all_batches, source_id="S001",
            raw_material_lot_id="RM-001",
            exclude_batch_id="B1",
            as_of=BASE + timedelta(days=5),
        )
        assert len(related) == 1
        assert related[0].batch_id == "B2"


class TestHoldReinspection:
    """BR-08 + BR-09: ON_HOLD reinspection flow — end-to-end unit tests.

    Joseph Mangaly (2463031)
    """

    def _make_released_batch(
        self,
        batch_id,
        source_id="S001",
        raw_lot="RM-001",
        lot_size=200,
        release_ts=None,
    ):
        ref = datetime(2026, 1, 1)
        release_ts = release_ts or ref
        b = Batch(
            batch_id=batch_id, product_id="P001",
            source_id=source_id, source_type="SUPPLIER",
            lot_size=lot_size, raw_material_lot_id=raw_lot,
            manufacture_date=ref - timedelta(days=30),
            expiry_date=ref + timedelta(days=300),
            total_shelf_life_days=365,
        )
        b.transition_to(BatchState.UNDER_INSPECTION, "test", ref)
        b.transition_to(BatchState.RELEASED, "released", release_ts)
        b.released_at = release_ts
        return b

    def test_on_hold_to_under_inspection_is_legal(self):
        """ON_HOLD -> UNDER_INSPECTION is now a legal transition (BR-08)."""
        b = self._make_released_batch("B-HOLD-TEST")
        b.transition_to(BatchState.ON_HOLD, "hold", datetime(2026, 1, 15))
        b.transition_to(BatchState.UNDER_INSPECTION, "reinspect", datetime(2026, 1, 16))
        assert b.state == BatchState.UNDER_INSPECTION

    def test_hold_reinspection_sets_flag(self):
        """begin_hold_inspection sets hold_reinspection=True and transitions state."""
        lc = LifecycleEngine()
        b = self._make_released_batch("B-FLAG")
        b.transition_to(BatchState.ON_HOLD, "hold", datetime(2026, 1, 10))
        lc.begin_hold_inspection(b, datetime(2026, 1, 15))
        assert b.state == BatchState.UNDER_INSPECTION
        assert b.hold_reinspection is True

    def test_hold_reinspection_double_sample_size(self, plan_loader, default_defect_configs):
        """ON_HOLD reinspection uses double sample size (BR-08)."""
        from src.inspection_engine import InspectionEngine
        from src.supplier_service import SupplierService
        BASE = datetime(2026, 1, 1)

        engine = InspectionEngine(plan_loader)
        ss = SupplierService()
        ss.register_supplier("S001", "Test")
        source = ss.get_supplier("S001")

        b = self._make_released_batch("B-DOUBLE", lot_size=200, release_ts=BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE + timedelta(days=5))
        engine.begin_hold_inspection(b, source, BASE + timedelta(days=10))
        assert b.hold_reinspection is True

        # Code G (lot=200), major AQL 1.0, NORMAL severity -> n=32 -> doubled=64
        entry = plan_loader.lookup("G", 1.0, source.severity)
        expected_n = min(entry.sample_size * 2, 200)

        ts = BASE + timedelta(days=10)
        defects = {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        decision, _ = engine.record_result(
            batch=b, source=source, defect_configs=default_defect_configs,
            defects=defects, sampled_at=ts, recorded_at=ts,
        )
        assert decision.sample_size == expected_n
        assert "BR-08" in decision.rule_ids

    def test_hold_reinspection_pass_releases_batch(self, plan_loader, default_defect_configs):
        """Successful ON_HOLD reinspection -> RELEASED."""
        from src.inspection_engine import InspectionEngine
        from src.supplier_service import SupplierService
        BASE = datetime(2026, 1, 1)

        engine = InspectionEngine(plan_loader)
        ss = SupplierService()
        ss.register_supplier("S001", "Test")
        source = ss.get_supplier("S001")

        b = self._make_released_batch("B-PASS", lot_size=200, release_ts=BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE + timedelta(days=5))
        engine.begin_hold_inspection(b, source, BASE + timedelta(days=10))

        ts = BASE + timedelta(days=10)
        defects = {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        decision, _ = engine.record_result(
            batch=b, source=source, defect_configs=default_defect_configs,
            defects=defects, sampled_at=ts, recorded_at=ts,
        )
        engine.apply_decision(b, decision, ts)
        assert b.state == BatchState.RELEASED

    def test_hold_reinspection_fail_rejects_batch(self, plan_loader, default_defect_configs):
        """Failed ON_HOLD reinspection (non-critical) -> REJECTED."""
        from src.inspection_engine import InspectionEngine
        from src.supplier_service import SupplierService
        from src.models import InspectionSeverity
        BASE = datetime(2026, 1, 1)

        engine = InspectionEngine(plan_loader)
        ss = SupplierService()
        ss.register_supplier("S001", "Test")
        source = ss.get_supplier("S001")

        b = self._make_released_batch("B-FAIL", lot_size=200, release_ts=BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE + timedelta(days=5))
        engine.begin_hold_inspection(b, source, BASE + timedelta(days=10))

        ts = BASE + timedelta(days=10)
        # major defects = Re -> rejection
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
        defects = {DefectClass.CRITICAL: 0, DefectClass.MAJOR: entry.re, DefectClass.MINOR: 0}
        decision, _ = engine.record_result(
            batch=b, source=source, defect_configs=default_defect_configs,
            defects=defects, sampled_at=ts, recorded_at=ts,
        )
        engine.apply_decision(b, decision, ts)
        assert b.state == BatchState.REJECTED

    def test_hold_reinspection_flag_reset_after_record(self, plan_loader, default_defect_configs):
        """hold_reinspection flag is reset to False after record_result."""
        from src.inspection_engine import InspectionEngine
        from src.supplier_service import SupplierService
        BASE = datetime(2026, 1, 1)

        engine = InspectionEngine(plan_loader)
        ss = SupplierService()
        ss.register_supplier("S001", "Test")
        source = ss.get_supplier("S001")

        b = self._make_released_batch("B-RESET", lot_size=200, release_ts=BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE + timedelta(days=5))
        engine.begin_hold_inspection(b, source, BASE + timedelta(days=10))
        assert b.hold_reinspection is True

        ts = BASE + timedelta(days=10)
        defects = {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        engine.record_result(
            batch=b, source=source, defect_configs=default_defect_configs,
            defects=defects, sampled_at=ts, recorded_at=ts,
        )
        assert b.hold_reinspection is False

