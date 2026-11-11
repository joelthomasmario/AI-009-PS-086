"""
test_integration.py – End-to-end integration tests for the AQL Engine.

Shared – AI-009
Team: AI-009  Section: 6BTAI

Tests complete inspection workflows across all BR rules.
"""

from __future__ import annotations

import os
import pytest
from datetime import datetime, timedelta
from typing import Dict, List

from src.models import (
    Batch, BatchDecision, BatchState,
    DefectClass, InspectionSeverity,
    RecallRecord, Supplier,
)
from src.inspection_engine import InspectionEngine
from src.product_service import ProductService
from src.supplier_service import SupplierService
from src.command_parser import CommandParser
from src.report_generator import ReportGenerator

BASE = datetime(2026, 1, 15, 10, 0, 0)
PLAN_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sampling_plan.csv")


def _create_infra(plan_loader):
    ps = ProductService()
    ss = SupplierService()
    ps.register("P001", "Widget", total_shelf_life_days=365)
    ss.register_supplier("S001", "Acme Corp")
    engine = InspectionEngine(plan_loader)
    return ps, ss, engine


def _run_one_batch(engine, ps, ss, batch_id, lot_size, defects, batch_offset_days=0):
    """Run one complete inspection cycle, returning decision."""
    product = ps.get("P001")
    source = ss.get_supplier("S001")
    ts = BASE + timedelta(days=batch_offset_days)

    batch = Batch(
        batch_id=batch_id, product_id="P001",
        source_id="S001", source_type="SUPPLIER",
        lot_size=lot_size, raw_material_lot_id="RM-001",
        manufacture_date=ts - timedelta(days=30),
        expiry_date=ts + timedelta(days=300),
        total_shelf_life_days=365,
    )
    engine.begin_inspection(batch, source, ts)

    decision, sw_records = engine.record_result(
        batch=batch, source=source,
        defect_configs=product.defect_configs,
        defects=defects,
        sampled_at=ts,
        recorded_at=ts,
    )
    engine.apply_decision(batch, decision, ts)
    return batch, decision, sw_records


class TestCompleteInspectionWorkflow:
    """Full workflow: register, inspect, decide, switch."""

    def test_accepted_batch_is_released(self, plan_loader):
        ps, ss, engine = _create_infra(plan_loader)
        batch, decision, _ = _run_one_batch(
            engine, ps, ss, "B001", 200,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        )
        assert batch.state == BatchState.RELEASED

    def test_critical_defect_batch_is_rejected(self, plan_loader):
        ps, ss, engine = _create_infra(plan_loader)
        batch, decision, _ = _run_one_batch(
            engine, ps, ss, "B001", 200,
            {DefectClass.CRITICAL: 1, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        )
        assert batch.state == BatchState.REJECTED

    def test_tightened_switch_after_two_rejections(self, plan_loader):
        ps, ss, engine = _create_infra(plan_loader)
        source = ss.get_supplier("S001")

        # Reject batch 1
        _run_one_batch(engine, ps, ss, "B1", 200,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 2, DefectClass.MINOR: 0}, 0)
        assert source.severity == InspectionSeverity.NORMAL

        # Accept batch 2
        _run_one_batch(engine, ps, ss, "B2", 200,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}, 1)

        # Reject batch 3 → 2 rejections in 3 batches → TIGHTENED
        _run_one_batch(engine, ps, ss, "B3", 200,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 2, DefectClass.MINOR: 0}, 2)
        assert source.severity == InspectionSeverity.TIGHTENED

    def test_full_rework_cycle(self, plan_loader):
        """Reject → rework → reinspect → released."""
        ps, ss, engine = _create_infra(plan_loader)
        product = ps.get("P001")
        source = ss.get_supplier("S001")
        ts = BASE

        batch = Batch(
            batch_id="B-RW", product_id="P001",
            source_id="S001", source_type="SUPPLIER",
            lot_size=200, raw_material_lot_id="RM-001",
            manufacture_date=ts - timedelta(days=30),
            expiry_date=ts + timedelta(days=300),
            total_shelf_life_days=365,
        )
        engine.begin_inspection(batch, source, ts)

        # First inspection: major defects at Re
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
        defects = {DefectClass.CRITICAL: 0, DefectClass.MAJOR: entry.re, DefectClass.MINOR: 0}
        decision, _ = engine.record_result(
            batch, source, product.defect_configs, defects, ts, ts
        )
        engine.apply_decision(batch, decision, ts)
        assert batch.state == BatchState.REJECTED

        # Rework (major = Re = 2×Re/2, so eligible if Re ≤ 2×Re)
        major_re = entry.re
        success, reason = engine.begin_rework(batch, major_re, ts)
        # Major count = Re; eligible only if Re ≤ 2×Re (always true for Re > 0)
        assert success is True
        engine.begin_reinspection(batch, ts)
        assert batch.state == BatchState.UNDER_INSPECTION

        # Reinspect with 0 defects → should be TIGHTENED severity
        decision2, _ = engine.record_result(
            batch, source, product.defect_configs,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
            ts + timedelta(hours=1),
            ts + timedelta(hours=1),
            rework_round=1,
        )
        engine.apply_decision(batch, decision2, ts + timedelta(hours=1))
        assert batch.state == BatchState.RELEASED


class TestCommandParserIntegration:
    """Integration test through the command parser."""

    def test_process_command_file(self, plan_loader, tmp_path):
        ps = ProductService()
        ss = SupplierService()
        engine = InspectionEngine(plan_loader)
        batches: Dict[str, Batch] = {}
        decisions: List[BatchDecision] = []
        switching: List = []
        recalls: List[RecallRecord] = []

        parser = CommandParser(engine, ps, ss, batches, decisions, switching, recalls)

        # Wide header covering all command fields. Each row populates only the
        # columns its command needs; the rest stay empty.
        header = (
            "command,product_id,name,total_shelf_life_days,supplier_id,"
            "batch_id,source_id,source_type,lot_size,raw_material_lot_id,"
            "manufacture_date,expiry_date,critical,major,minor,sampled_at,recorded_at"
        )
        rows = [
            "REGISTER_PRODUCT,P001,Widget A,365,,,,,,,,,,,,",
            "REGISTER_SUPPLIER,,Acme Corp,,S001,,,,,,,,,,,",
            "CREATE_BATCH,P001,,,S001,B001,S001,SUPPLIER,200,RM-001,2026-01-01,2026-12-31,,,,,",
            "BEGIN_INSPECTION,,,,,B001,,,,,,,,,,,",
            "RECORD_RESULT,,,,,B001,,,,,,,0,0,0,2026-01-15T10:00:00,2026-01-15T10:00:00",
        ]
        cmd_file = tmp_path / "commands.csv"
        cmd_file.write_text(header + "\n" + "\n".join(rows) + "\n")

        results = parser.process_file(str(cmd_file))
        assert len(results) >= 5
        assert "B001" in batches, (
            "B001 not in batches. Results:\n" +
            "\n".join(
                f"  Row {r.row_num}: [{'OK' if r.success else 'FAIL'}] {r.command}: {r.message}"
                for r in results
            )
        )
        assert len(decisions) >= 1

    def test_invalid_command_returns_failure(self, plan_loader, tmp_path):
        ps = ProductService()
        ss = SupplierService()
        engine = InspectionEngine(plan_loader)
        batches: Dict[str, Batch] = {}
        decisions = []
        switching = []
        recalls = []

        parser = CommandParser(engine, ps, ss, batches, decisions, switching, recalls)
        cmd_file = tmp_path / "invalid.csv"
        cmd_file.write_text("command,product_id\nINVALID_CMD,P001\n")
        results = parser.process_file(str(cmd_file))
        assert any(not r.success for r in results)
        assert any("Unknown command" in r.message for r in results)

    def test_duplicate_product_id_fails(self, plan_loader, tmp_path):
        ps = ProductService()
        ss = SupplierService()
        engine = InspectionEngine(plan_loader)
        batches: Dict[str, Batch] = {}
        decisions = []
        switching = []
        recalls = []

        parser = CommandParser(engine, ps, ss, batches, decisions, switching, recalls)
        cmd_file = tmp_path / "dup.csv"
        cmd_file.write_text(
            "command,product_id,name,total_shelf_life_days\n"
            "REGISTER_PRODUCT,P001,Widget,365\n"
            "REGISTER_PRODUCT,P001,Duplicate,100\n"  # duplicate ID
        )
        results = parser.process_file(str(cmd_file))
        assert results[0].success
        assert not results[1].success
        assert "already registered" in results[1].message


class TestReportGeneration:
    """Verify that all 5 report files are generated correctly."""

    def test_all_reports_generated(self, plan_loader, tmp_path):
        ps, ss, engine = _create_infra(plan_loader)
        batch, decision, sw_records = _run_one_batch(
            engine, ps, ss, "BRPT-001", 200,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        )
        reporter = ReportGenerator(str(tmp_path))
        paths = reporter.generate_all(
            decisions=[decision],
            switching_records=sw_records,
            batches=[batch],
            recalls=[],
        )
        for name, path in paths.items():
            assert os.path.exists(path), f"Report {name} not generated: {path}"

    def test_batch_decisions_csv_has_correct_columns(self, plan_loader, tmp_path):
        import csv
        ps, ss, engine = _create_infra(plan_loader)
        _, decision, _ = _run_one_batch(
            engine, ps, ss, "BRPT-002", 200,
            {DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0}
        )
        reporter = ReportGenerator(str(tmp_path))
        path = reporter.write_batch_decisions([decision])
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            assert "batch_id" in reader.fieldnames
            assert "decision" in reader.fieldnames
            assert "is_late" in reader.fieldnames
            assert "rule_ids" in reader.fieldnames


class TestHoldReinspectionIntegration:
    """BR-08 + BR-09: Full end-to-end ON_HOLD reinspection + cascade recall.

    Joseph Mangaly (2463031)
    """

    def _make_and_release_batch(self, engine, ps, ss, batch_id, raw_lot, lot_size=200):
        """Create a batch, inspect it cleanly, and return it RELEASED."""
        product = ps.get("P001")
        source = ss.get_supplier("S001")
        ts = BASE

        batch = Batch(
            batch_id=batch_id, product_id="P001",
            source_id="S001", source_type="SUPPLIER",
            lot_size=lot_size, raw_material_lot_id=raw_lot,
            manufacture_date=ts - timedelta(days=30),
            expiry_date=ts + timedelta(days=300),
            total_shelf_life_days=365,
        )
        engine.begin_inspection(batch, source, ts)
        decision, _ = engine.record_result(
            batch=batch, source=source,
            defect_configs=product.defect_configs,
            defects={DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
            sampled_at=ts, recorded_at=ts,
        )
        engine.apply_decision(batch, decision, ts)
        assert batch.state == BatchState.RELEASED, f"{batch_id} expected RELEASED, got {batch.state}"
        return batch

    def test_hold_reinspect_critical_triggers_recall_cascade(self, plan_loader):
        """HOLD -> reinspect -> critical defect -> RECALL -> cascades to same-lot batches."""
        from src.models import InspectionSeverity
        ps, ss, engine = _create_infra(plan_loader)
        product = ps.get("P001")
        source = ss.get_supplier("S001")

        # B1 and B2 share RM-001 (both released); B3 is a different lot
        b1 = self._make_and_release_batch(engine, ps, ss, "B-RC1", "RM-001")
        b2 = self._make_and_release_batch(engine, ps, ss, "B-RC2", "RM-001")
        b3 = self._make_and_release_batch(engine, ps, ss, "B-RC3", "RM-002")

        # Place B1 ON_HOLD within 30 days
        ok, msg = engine.place_on_hold(b1, "Related batch critical defect", BASE + timedelta(days=5))
        assert ok, f"place_on_hold failed: {msg}"
        assert b1.state == BatchState.ON_HOLD

        # Begin ON_HOLD reinspection -> ON_HOLD -> UNDER_INSPECTION, hold_reinspection=True
        engine.begin_hold_inspection(b1, source, BASE + timedelta(days=10))
        assert b1.state == BatchState.UNDER_INSPECTION
        assert b1.hold_reinspection is True

        # Confirm double sample size is used
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
        expected_n = min(entry.sample_size * 2, b1.lot_size)

        # Record result with critical defect -> REJECTED; hold_reinspection=False after
        ts = BASE + timedelta(days=10)
        decision, _ = engine.record_result(
            batch=b1, source=source,
            defect_configs=product.defect_configs,
            defects={DefectClass.CRITICAL: 1, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
            sampled_at=ts, recorded_at=ts,
        )
        assert decision.sample_size == expected_n, (
            f"Expected double sample={expected_n}, got {decision.sample_size}"
        )
        assert "BR-08" in decision.rule_ids
        assert b1.hold_reinspection is False  # flag was reset

        # Apply decision -> B1 becomes REJECTED (critical defect)
        engine.apply_decision(b1, decision, ts)
        assert b1.state == BatchState.REJECTED

        # Trigger cascade recall (normally done by command_parser)
        all_batches = [b1, b2, b3]
        recall = engine.trigger_recall(
            all_batches, b1,
            "Critical defect found during ON_HOLD reinspection (BR-09)",
            ts,
        )

        # B2 shares RM-001 and is RELEASED -> should be RECALLED
        assert "B-RC2" in recall.recalled_batch_ids, f"B-RC2 not recalled; got {recall.recalled_batch_ids}"
        assert b2.state == BatchState.RECALLED
        # B3 has different lot -> NOT recalled
        assert "B-RC3" not in recall.recalled_batch_ids
        assert b3.state == BatchState.RELEASED
        assert recall.rule_id == "BR-09"

    def test_hold_reinspect_no_critical_releases_batch(self, plan_loader):
        """HOLD -> reinspect -> pass (0 defects) -> RELEASED (no recall)."""
        ps, ss, engine = _create_infra(plan_loader)
        product = ps.get("P001")
        source = ss.get_supplier("S001")

        b = self._make_and_release_batch(engine, ps, ss, "B-OK-HOLD", "RM-HOLD")

        # Place ON_HOLD
        ok, msg = engine.place_on_hold(b, "Test hold", BASE + timedelta(days=5))
        assert ok, f"place_on_hold failed: {msg}"
        assert b.state == BatchState.ON_HOLD

        # Reinspect with 0 defects -> should pass and release
        ts = BASE + timedelta(days=10)
        engine.begin_hold_inspection(b, source, ts)
        assert b.state == BatchState.UNDER_INSPECTION
        assert b.hold_reinspection is True

        d2, _ = engine.record_result(
            batch=b, source=source, defect_configs=product.defect_configs,
            defects={DefectClass.CRITICAL: 0, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
            sampled_at=ts, recorded_at=ts,
        )
        assert "BR-08" in d2.rule_ids
        assert b.hold_reinspection is False

        engine.apply_decision(b, d2, ts)
        assert b.state == BatchState.RELEASED
