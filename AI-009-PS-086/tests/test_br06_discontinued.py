"""
test_br06_discontinued.py – Tests for BR-06: DISCONTINUED state management.

Joselet K Jaison (2463030)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime

from src.switching_engine import SwitchingEngine
from src.models import InspectionSeverity, Supplier, CorrectiveAction, Batch, BatchState
from src.inspection_engine import InspectionEngine

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _discontinued_supplier():
    return Supplier(
        supplier_id="S-DISC",
        name="Discontinued Supplier",
        severity=InspectionSeverity.DISCONTINUED,
        corrective_action_registered=False,
    )


def _make_batch(batch_id="B001", source_id="S-DISC", lot_size=200):
    return Batch(
        batch_id=batch_id, product_id="P001",
        source_id=source_id, source_type="SUPPLIER",
        lot_size=lot_size, raw_material_lot_id="RM-001",
        manufacture_date=BASE,
    )


class TestDiscontinued:
    """BR-06: Inspection forbidden on DISCONTINUED source without corrective action."""

    def test_inspection_blocked_when_discontinued(self, engine):
        s = _discontinued_supplier()
        b = _make_batch()
        with pytest.raises(PermissionError, match="DISCONTINUED"):
            engine.begin_inspection(b, s)

    def test_corrective_action_switches_to_tightened(self):
        sw = SwitchingEngine()
        s = _discontinued_supplier()
        action = CorrectiveAction(
            action_id="CA-001",
            source_id="S-DISC",
            description="Root cause identified and fixed.",
            registered_at=BASE,
        )
        record = sw.apply_corrective_action(s, action.action_id, BASE)
        assert s.severity == InspectionSeverity.TIGHTENED
        assert record.previous_severity == InspectionSeverity.DISCONTINUED
        assert record.new_severity == InspectionSeverity.TIGHTENED
        assert record.rule_id == "BR-06"

    def test_corrective_action_on_non_discontinued_raises(self):
        sw = SwitchingEngine()
        s = Supplier("S-NORM", "Normal Supplier", severity=InspectionSeverity.NORMAL)
        with pytest.raises(ValueError, match="not DISCONTINUED"):
            sw.apply_corrective_action(s, "CA-001", BASE)

    def test_inspection_allowed_after_corrective_action(self, engine, plan_loader, default_defect_configs):
        s = _discontinued_supplier()
        sw = SwitchingEngine()
        # Register corrective action
        action = CorrectiveAction("CA-002", "S-DISC", "Fixed", registered_at=BASE)
        sw.apply_corrective_action(s, action.action_id, BASE)

        # Now inspection should be allowed (source is TIGHTENED)
        b = _make_batch("B-CA")
        b_state = b.state
        # begin_inspection should not raise
        engine.begin_inspection(b, s, BASE)
        assert b.state == BatchState.UNDER_INSPECTION

    def test_missing_corrective_action_message_mentions_br06(self, engine):
        s = _discontinued_supplier()
        b = _make_batch("B-DISC2")
        with pytest.raises(PermissionError) as exc_info:
            engine.begin_inspection(b, s)
        assert "BR-06" in str(exc_info.value)

