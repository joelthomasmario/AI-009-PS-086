"""
test_br02_defect_classification.py – Tests for BR-02: Defect classification.

Joel Thomas Mario J (2463029)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime

from src.models import (
    Batch,
    BatchState,
    DefectClass,
    DefectClassConfig,
    DecisionCode,
    InspectionResult,
    InspectionSeverity,
    Supplier,
)
from src.sampling_engine import SamplingEngine


BASE_TS = datetime(2026, 1, 15, 10, 0, 0)


def _make_result(batch_id, sample_size, critical=0, major=0, minor=0):
    return InspectionResult(
        batch_id=batch_id,
        sample_size=sample_size,
        defects={
            DefectClass.CRITICAL: critical,
            DefectClass.MAJOR: major,
            DefectClass.MINOR: minor,
        },
        sampled_at=BASE_TS,
        recorded_at=BASE_TS,
    )


class TestDefectClassification:
    """BR-02: Each defect class is evaluated independently."""

    def test_all_zero_defects_accepted(self, plan_loader, default_defect_configs):
        engine = SamplingEngine(plan_loader)
        result = _make_result("B001", 32, critical=0, major=0, minor=0)
        decision = engine.evaluate("B001", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is True
        assert decision.decision_code == DecisionCode.ACCEPTED

    def test_critical_defect_one_causes_rejection(self, plan_loader, default_defect_configs):
        """BR-02: Critical defects ≥ 1 always cause rejection."""
        engine = SamplingEngine(plan_loader)
        result = _make_result("B002", 32, critical=1, major=0, minor=0)
        decision = engine.evaluate("B002", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is False
        assert decision.decision_code == DecisionCode.REJECTED_CRITICAL

    def test_critical_defect_auto_reject_flag(self, plan_loader, default_defect_configs):
        """The critical PerClassEvaluation should have critical_auto_reject=True."""
        engine = SamplingEngine(plan_loader)
        result = _make_result("B003", 32, critical=1)
        decision = engine.evaluate("B003", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        crit_ev = next(e for e in decision.per_class if e.defect_class == DefectClass.CRITICAL)
        assert crit_ev.critical_auto_reject is True

    def test_major_defect_at_re_causes_rejection(self, plan_loader, default_defect_configs):
        """BR-02: Defects at Re are rejected (not just > Re)."""
        engine = SamplingEngine(plan_loader)
        # Lot 200 → code G, NORMAL, major AQL 1.0 → sample=32, Ac=1, Re=2
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
        re_val = entry.re
        result = _make_result("B004", entry.sample_size, critical=0, major=re_val, minor=0)
        decision = engine.evaluate("B004", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is False

    def test_major_defect_at_ac_accepted(self, plan_loader, default_defect_configs):
        """BR-02: Defects exactly at Ac → accepted (EC-2)."""
        engine = SamplingEngine(plan_loader)
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
        ac_val = entry.ac
        result = _make_result("B005", entry.sample_size, critical=0, major=ac_val, minor=0)
        decision = engine.evaluate("B005", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is True, (
            f"Expected accepted with major={ac_val} (Ac={ac_val})"
        )

    def test_minor_defect_at_re_causes_rejection(self, plan_loader, default_defect_configs):
        """BR-02: Minor class evaluated independently – reaching Re rejects."""
        engine = SamplingEngine(plan_loader)
        entry = plan_loader.lookup("G", 2.5, InspectionSeverity.NORMAL)
        result = _make_result("B006", entry.sample_size, critical=0, major=0, minor=entry.re)
        decision = engine.evaluate("B006", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is False

    def test_minor_defect_below_re_accepted(self, plan_loader, default_defect_configs):
        engine = SamplingEngine(plan_loader)
        entry = plan_loader.lookup("G", 2.5, InspectionSeverity.NORMAL)
        result = _make_result("B007", entry.sample_size, critical=0, major=0, minor=entry.re - 1)
        decision = engine.evaluate("B007", 200, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is True

    def test_default_aql_values(self):
        """BR-02: Default AQL values are CRITICAL=0.065, MAJOR=1.0, MINOR=2.5."""
        configs = DefectClassConfig.defaults()
        aql_map = {c.defect_class: c.aql for c in configs}
        assert aql_map[DefectClass.CRITICAL] == 0.065
        assert aql_map[DefectClass.MAJOR] == 1.0
        assert aql_map[DefectClass.MINOR] == 2.5

    def test_ec2_defects_exactly_equal_to_ac(self, plan_loader, default_defect_configs):
        """EC-2: Defects exactly equal to Ac → ACCEPTED."""
        engine = SamplingEngine(plan_loader)
        entry = plan_loader.lookup("H", 2.5, InspectionSeverity.NORMAL)
        ac_val = entry.ac
        result = _make_result("B-EC2", entry.sample_size, minor=ac_val)
        decision = engine.evaluate("B-EC2", 300, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is True, f"Ac={ac_val}, minor={ac_val} should be ACCEPTED"

    def test_ec3_defects_exactly_equal_to_re(self, plan_loader, default_defect_configs):
        """EC-3: Defects exactly equal to Re → REJECTED."""
        engine = SamplingEngine(plan_loader)
        entry = plan_loader.lookup("H", 2.5, InspectionSeverity.NORMAL)
        re_val = entry.re
        result = _make_result("B-EC3", entry.sample_size, minor=re_val)
        decision = engine.evaluate("B-EC3", 300, default_defect_configs, result, InspectionSeverity.NORMAL)
        assert decision.overall_accepted is False, f"Re={re_val}, minor={re_val} should be REJECTED"

