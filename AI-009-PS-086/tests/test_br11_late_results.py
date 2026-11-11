"""
test_br11_late_results.py – Tests for BR-11: 48-hour recording window.

Shared – AI-009
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from src.lifecycle_engine import LifecycleEngine
from src.models import InspectionResult, DefectClass

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _result(offset_hours: float) -> InspectionResult:
    return InspectionResult(
        batch_id="B-LATE",
        sample_size=32,
        defects={DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
        sampled_at=BASE,
        recorded_at=BASE + timedelta(hours=offset_hours),
    )


class TestLateResults:
    """BR-11: Results recorded > 48 hours after sampling are marked LATE."""

    def test_exactly_48_hours_is_not_late(self):
        """EC-10: Result recorded exactly 48 hours after sampling → NOT LATE."""
        lc = LifecycleEngine()
        result = _result(48.0)
        lc.mark_late(result)
        assert result.is_late is False, "Exactly 48h should NOT be late per BR-11"

    def test_48_hours_plus_one_second_is_late(self):
        """48h + 1s → LATE."""
        lc = LifecycleEngine()
        result = InspectionResult(
            batch_id="B-LATE2",
            sample_size=32,
            defects={DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
            sampled_at=BASE,
            recorded_at=BASE + timedelta(hours=48, seconds=1),
        )
        lc.mark_late(result)
        assert result.is_late is True

    def test_recorded_before_48_hours_not_late(self):
        lc = LifecycleEngine()
        result = _result(47.9)
        lc.mark_late(result)
        assert result.is_late is False

    def test_recorded_well_after_48_hours_is_late(self):
        lc = LifecycleEngine()
        result = _result(72.0)  # 3 days later
        lc.mark_late(result)
        assert result.is_late is True

    def test_recorded_at_same_time_as_sampled_not_late(self):
        lc = LifecycleEngine()
        result = _result(0.0)
        lc.mark_late(result)
        assert result.is_late is False

    def test_late_result_rule_id_in_decision(self, engine, plan_loader, default_defect_configs):
        """LATE results must include BR-11 in the decision rule_ids."""
        from datetime import datetime
        from src.models import (
            Batch, BatchState, DefectClass, InspectionSeverity,
            Supplier,
        )

        s = Supplier("S-LATE", "Late Supplier", severity=InspectionSeverity.NORMAL)
        b = Batch(
            batch_id="B-LATEDEC", product_id="P001",
            source_id="S-LATE", source_type="SUPPLIER",
            lot_size=200, raw_material_lot_id="RM-001",
            manufacture_date=BASE,
        )
        b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)

        from src.product_service import ProductService
        ps = ProductService()
        ps.register("P001", "Widget", total_shelf_life_days=0)

        sampled = BASE
        # Record > 48h later
        recorded = BASE + timedelta(hours=49)
        defects = {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}

        decision, _ = engine.record_result(
            batch=b, source=s,
            defect_configs=default_defect_configs,
            defects=defects,
            sampled_at=sampled,
            recorded_at=recorded,
        )
        assert decision.is_late is True
        assert "BR-11" in decision.rule_ids

