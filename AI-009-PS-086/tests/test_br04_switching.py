"""
test_br04_switching.py – Tests for BR-04: Severity switching rules
(NORMAL ↔ TIGHTENED, TIGHTENED → DISCONTINUED, NORMAL → REDUCED).

Joselet K Jaison (2463030)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from src.switching_engine import SwitchingEngine
from src.models import InspectionSeverity, Supplier


BASE = datetime(2026, 1, 15, 10, 0, 0)


def _supplier(sid="S001", severity=InspectionSeverity.NORMAL):
    return Supplier(supplier_id=sid, name="Test Supplier", severity=severity)


class TestNormalToTightened:
    """BR-04: 2 rejections in 5 consecutive batches → TIGHTENED."""

    def test_one_rejection_does_not_trigger_tightened(self):
        sw = SwitchingEngine()
        s = _supplier()
        # 1 rejection in 1 batch → no switch
        sw.process_decision(s, "B1", accepted=False, is_late=False,
                            total_defects=0, reduced_ac=0,
                            between_ac_and_re=False, inspection_timestamp=BASE)
        assert s.severity == InspectionSeverity.NORMAL

    def test_two_rejections_in_five_trigger_tightened(self):
        """EC-5: Second rejection when first rejection is exactly the 5th-previous batch."""
        sw = SwitchingEngine()
        s = _supplier()
        # Batch 1: reject
        sw.process_decision(s, "B1", False, False, 0, 0, False, BASE)
        # Batches 2-4: accept
        for i in range(2, 5):
            sw.process_decision(s, f"B{i}", True, False, 0, 0, False, BASE + timedelta(days=i))
        # Batch 5: reject → 2 rejections in last 5 → TIGHTENED
        sw.process_decision(s, "B5", False, False, 0, 0, False, BASE + timedelta(days=5))
        assert s.severity == InspectionSeverity.TIGHTENED

    def test_ec5_first_rejection_exactly_fifth_previous(self):
        """EC-5: First rejection is exactly the 5th previous batch from the trigger."""
        sw = SwitchingEngine()
        s = _supplier()
        # Window is 5 slots. Fill: reject, accept, accept, accept, reject → 2 rejects
        decisions = [False, True, True, True, False]
        for i, acc in enumerate(decisions):
            sw.process_decision(s, f"B{i}", acc, False, 0, 0, False, BASE + timedelta(days=i))
        assert s.severity == InspectionSeverity.TIGHTENED

    def test_two_rejections_outside_window_no_switch(self):
        """Two rejections more than 5 batches apart → no TIGHTENED switch."""
        sw = SwitchingEngine()
        s = _supplier()
        # First rejection
        sw.process_decision(s, "B1", False, False, 0, 0, False, BASE)
        # 5 acceptances (push B1 out of 5-window)
        for i in range(2, 7):
            sw.process_decision(s, f"B{i}", True, False, 0, 0, False, BASE + timedelta(days=i))
        assert s.severity == InspectionSeverity.NORMAL
        # Second rejection – B1 is now outside the 5-batch window
        sw.process_decision(s, "B7", False, False, 0, 0, False, BASE + timedelta(days=7))
        assert s.severity == InspectionSeverity.NORMAL


class TestTightenedToNormal:
    """BR-04: 5 consecutive acceptances while TIGHTENED → NORMAL."""

    def test_five_accepts_while_tightened_switch_to_normal(self):
        sw = SwitchingEngine()
        s = _supplier(severity=InspectionSeverity.TIGHTENED)
        for i in range(5):
            sw.process_decision(s, f"B{i}", True, False, 0, 0, False, BASE + timedelta(days=i))
        assert s.severity == InspectionSeverity.NORMAL

    def test_four_accepts_while_tightened_no_switch(self):
        sw = SwitchingEngine()
        s = _supplier(severity=InspectionSeverity.TIGHTENED)
        for i in range(4):
            sw.process_decision(s, f"B{i}", True, False, 0, 0, False, BASE + timedelta(days=i))
        assert s.severity == InspectionSeverity.TIGHTENED

    def test_rejection_resets_tightened_accept_counter(self):
        sw = SwitchingEngine()
        s = _supplier(severity=InspectionSeverity.TIGHTENED)
        # 3 accepts, 1 reject, then 5 accepts needed
        for i in range(3):
            sw.process_decision(s, f"B{i}", True, False, 0, 0, False, BASE + timedelta(days=i))
        sw.process_decision(s, "BX", False, False, 0, 0, False, BASE + timedelta(days=4))
        assert s.consecutive_accepts == 0  # reset by rejection
        assert s.severity == InspectionSeverity.TIGHTENED


class TestTightenedToDiscontinued:
    """BR-04: 5 cumulative rejections while TIGHTENED → DISCONTINUED."""

    def test_five_cumulative_rejections_discontinued(self):
        sw = SwitchingEngine()
        s = _supplier(severity=InspectionSeverity.TIGHTENED)
        # Mix accepts and rejects – cumulative rejections count is what matters
        decisions = [False, True, False, True, False, True, False, True, False]  # 5 rejects
        for i, acc in enumerate(decisions):
            sw.process_decision(s, f"B{i}", acc, False, 0, 0, False, BASE + timedelta(days=i))
            if s.severity == InspectionSeverity.DISCONTINUED:
                break
        assert s.severity == InspectionSeverity.DISCONTINUED

    def test_four_cumulative_rejections_still_tightened(self):
        sw = SwitchingEngine()
        s = _supplier(severity=InspectionSeverity.TIGHTENED)
        for i in range(4):
            sw.process_decision(s, f"B{i}", False, False, 0, 0, False, BASE + timedelta(days=i))
        assert s.severity == InspectionSeverity.TIGHTENED


class TestNormalToReduced:
    """BR-04: 10 consecutive acceptances + defects within REDUCED limit → REDUCED."""

    def test_ten_consecutive_accepts_switches_to_reduced(self, plan_loader, default_defect_configs):
        sw = SwitchingEngine()
        s = _supplier()
        # Lot 200 → code G, REDUCED, major 1.0 → Ac=1
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.REDUCED)
        reduced_ac = entry.ac  # 1 for code G

        for i in range(10):
            sw.process_decision(
                s, f"B{i}", True, False,
                total_defects=0,
                reduced_ac=reduced_ac,
                between_ac_and_re=False,
                inspection_timestamp=BASE + timedelta(days=i),
            )
        assert s.severity == InspectionSeverity.REDUCED

    def test_nine_accepts_no_switch(self, plan_loader):
        sw = SwitchingEngine()
        s = _supplier()
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.REDUCED)
        for i in range(9):
            sw.process_decision(
                s, f"B{i}", True, False, 0, entry.ac, False, BASE + timedelta(days=i)
            )
        assert s.severity == InspectionSeverity.NORMAL

    def test_late_results_do_not_count_toward_reduced(self, plan_loader):
        """BR-11: LATE results must not count toward NORMAL→REDUCED switching."""
        sw = SwitchingEngine()
        s = _supplier()
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.REDUCED)
        # 10 LATE acceptances → counter stays at 0
        for i in range(10):
            sw.process_decision(
                s, f"B{i}", True, is_late=True,
                total_defects=0, reduced_ac=entry.ac,
                between_ac_and_re=False,
                inspection_timestamp=BASE + timedelta(days=i),
            )
        assert s.severity == InspectionSeverity.NORMAL

    def test_defects_exceed_reduced_ac_prevents_switch(self, plan_loader):
        """If total defects > reduced Ac, NORMAL→REDUCED does not trigger."""
        sw = SwitchingEngine()
        s = _supplier()
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.REDUCED)
        for i in range(10):
            sw.process_decision(
                s, f"B{i}", True, False,
                total_defects=entry.ac + 1,  # exceeds limit
                reduced_ac=entry.ac,
                between_ac_and_re=False,
                inspection_timestamp=BASE + timedelta(days=i),
            )
        assert s.severity == InspectionSeverity.NORMAL

