"""
test_br07_rework.py – Tests for BR-07: Rework eligibility and reinspection.

Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime

from src.rework_engine import ReworkEngine
from src.models import (
    Batch, BatchState, DefectClass, InspectionResult, InspectionSeverity
)

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _rejected_batch(batch_id="B-REJ"):
    b = Batch(
        batch_id=batch_id, product_id="P001",
        source_id="S001", source_type="SUPPLIER",
        lot_size=200, raw_material_lot_id="RM-001",
        manufacture_date=BASE,
    )
    # Force to REJECTED state directly via transition
    b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)
    b.transition_to(BatchState.REJECTED, "test rejection", BASE)
    return b


def _result(critical=0, major=0, minor=0):
    return InspectionResult(
        batch_id="B-REJ",
        sample_size=32,
        defects={
            DefectClass.CRITICAL: critical,
            DefectClass.MAJOR: major,
            DefectClass.MINOR: minor,
        },
        sampled_at=BASE,
        recorded_at=BASE,
    )


class TestReworkEligibility:
    """BR-07: Rework eligibility rules."""

    def test_eligible_no_critical_major_within_2_re(self):
        rw = ReworkEngine()
        b = _rejected_batch()
        result = _result(critical=0, major=3, minor=0)
        major_re = 2  # so 2×Re = 4; major=3 ≤ 4 → eligible
        eligible, reason = rw.is_eligible(b, result, major_re)
        assert eligible is True

    def test_ec6_major_exactly_2_re_eligible(self):
        """EC-6: Major defects exactly equal to 2 × Re → eligible for rework."""
        rw = ReworkEngine()
        b = _rejected_batch()
        major_re = 2  # 2×Re = 4
        result = _result(critical=0, major=4, minor=0)  # exactly 2×Re
        eligible, reason = rw.is_eligible(b, result, major_re)
        assert eligible is True, f"Expected eligible but got: {reason}"

    def test_major_exceeds_2_re_not_eligible(self):
        """BR-07: Major > 2×Re → not eligible."""
        rw = ReworkEngine()
        b = _rejected_batch()
        major_re = 2  # 2×Re = 4
        result = _result(critical=0, major=5, minor=0)  # > 4 → ineligible
        eligible, reason = rw.is_eligible(b, result, major_re)
        assert eligible is False
        assert "2×Re" in reason or "2*Re" in reason or "2×Re" in reason or "2" in reason

    def test_critical_defect_prevents_rework(self):
        """BR-07: Any critical defect → not eligible."""
        rw = ReworkEngine()
        b = _rejected_batch()
        result = _result(critical=1, major=0, minor=0)
        eligible, reason = rw.is_eligible(b, result, major_re=4)
        assert eligible is False
        assert "critical" in reason.lower()

    def test_second_rejection_is_final(self):
        """BR-07: Second rejection → no rework allowed."""
        rw = ReworkEngine()
        b = _rejected_batch()
        b.rework_count = 1  # Already had one rework cycle
        result = _result(critical=0, major=0, minor=0)
        eligible, reason = rw.is_eligible(b, result, major_re=4)
        assert eligible is False
        assert "final" in reason.lower() or "second" in reason.lower()

    def test_non_rejected_batch_raises(self):
        """Rework eligibility check on non-REJECTED batch raises ValueError."""
        rw = ReworkEngine()
        b = Batch(
            batch_id="B-OK", product_id="P001",
            source_id="S001", source_type="SUPPLIER",
            lot_size=200, raw_material_lot_id="RM-001",
            manufacture_date=BASE,
        )
        # Batch is still in QUARANTINE
        result = _result()
        with pytest.raises(ValueError, match="not in REJECTED"):
            rw.is_eligible(b, result, major_re=4)


class TestReworkLifecycle:
    """BR-07: Rework state transitions."""

    def test_begin_rework_transitions_to_rework(self):
        rw = ReworkEngine()
        b = _rejected_batch()
        result = _result(critical=0, major=0, minor=0)
        eligible, _ = rw.is_eligible(b, result, major_re=4)
        assert eligible
        rw.begin_rework(b, BASE)
        assert b.state == BatchState.REWORK
        assert b.rework_count == 1

    def test_begin_reinspection_transitions_to_under_inspection(self):
        rw = ReworkEngine()
        b = _rejected_batch()
        rw.begin_rework(b, BASE)
        rw.begin_reinspection(b, BASE)
        assert b.state == BatchState.UNDER_INSPECTION

