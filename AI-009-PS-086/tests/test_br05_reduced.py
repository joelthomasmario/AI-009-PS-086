"""
test_br05_reduced.py – Tests for BR-05: REDUCED switching rules.

Joselet K Jaison (2463030)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from src.switching_engine import SwitchingEngine
from src.models import InspectionSeverity, Supplier


BASE = datetime(2026, 1, 15, 10, 0, 0)


def _supplier_reduced():
    s = Supplier(supplier_id="S-RED", name="Reduced Supplier", severity=InspectionSeverity.REDUCED)
    s.last_inspection_at = BASE
    return s


class TestReducedToNormal:
    """BR-05: Switching from REDUCED back to NORMAL."""

    def test_rejection_under_reduced_switches_to_normal(self):
        sw = SwitchingEngine()
        s = _supplier_reduced()
        sw.process_decision(s, "B1", False, False, 0, 0, False, BASE + timedelta(days=1))
        assert s.severity == InspectionSeverity.NORMAL

    def test_ec4_between_ac_and_re_accepted_switches_to_normal(self):
        """EC-4: Between-Ac-and-Re result under REDUCED → batch accepted, switch to NORMAL."""
        sw = SwitchingEngine()
        s = _supplier_reduced()
        # Pass between_ac_and_re=True (simulates result between Ac and Re)
        records = sw.process_decision(
            s, "B1", accepted=True,
            is_late=False, total_defects=1, reduced_ac=1,
            between_ac_and_re=True,
            inspection_timestamp=BASE + timedelta(days=1),
        )
        assert s.severity == InspectionSeverity.NORMAL
        # Must have produced a switching record
        assert any(r.rule_id == "BR-05" for r in records)

    def test_production_irregularity_gap_over_30_days(self):
        """BR-05: Gap > 30 days → production irregularity → switch to NORMAL."""
        sw = SwitchingEngine()
        s = _supplier_reduced()
        s.last_inspection_at = BASE
        # Inspection more than 30 days later
        late_ts = BASE + timedelta(days=31)
        records = sw.process_decision(
            s, "B1", True, False, 0, 0, False, late_ts
        )
        assert s.severity == InspectionSeverity.NORMAL
        assert any("irregularity" in r.event.lower() for r in records)

    def test_production_irregularity_exactly_30_days_no_switch(self):
        """BR-05: Gap of exactly 30 days is NOT an irregularity (> 30 required)."""
        sw = SwitchingEngine()
        s = _supplier_reduced()
        s.last_inspection_at = BASE
        ts_30 = BASE + timedelta(days=30)
        sw.process_decision(s, "B1", True, False, 0, 0, False, ts_30)
        assert s.severity == InspectionSeverity.REDUCED

    def test_clean_acceptance_under_reduced_no_switch(self):
        """Clean acceptance under REDUCED → stays REDUCED."""
        sw = SwitchingEngine()
        s = _supplier_reduced()
        sw.process_decision(s, "B1", True, False, 0, 1, False, BASE + timedelta(days=1))
        assert s.severity == InspectionSeverity.REDUCED

