"""
test_br09_recall.py – Tests for BR-09: Recall and cascade recall.

Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from src.recall_engine import RecallEngine
from src.models import Batch, BatchState, DefectClass, InspectionResult

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _batch(batch_id, state=BatchState.RELEASED, raw_lot="RM-001", expiry_offset_days=365):
    b = Batch(
        batch_id=batch_id, product_id="P001",
        source_id="S001", source_type="SUPPLIER",
        lot_size=100, raw_material_lot_id=raw_lot,
        manufacture_date=BASE,
        expiry_date=BASE + timedelta(days=expiry_offset_days),
    )
    # Transition to desired state
    if state in (BatchState.RELEASED, BatchState.ON_HOLD, BatchState.RECALLED):
        b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)
        if state == BatchState.RELEASED:
            b.transition_to(BatchState.RELEASED, "test", BASE)
        elif state == BatchState.ON_HOLD:
            b.transition_to(BatchState.RELEASED, "test", BASE)
            b.released_at = BASE
            b.transition_to(BatchState.ON_HOLD, "test", BASE)
        elif state == BatchState.RECALLED:
            b.transition_to(BatchState.RELEASED, "test", BASE)
            b.transition_to(BatchState.RECALLED, "test", BASE)
    return b


class TestRecallCascade:
    """BR-09: Recall cascade to batches sharing same raw-material lot."""

    def test_recall_all_non_expired_in_lot(self):
        re = RecallEngine()
        b1 = _batch("B1", state=BatchState.RELEASED, raw_lot="RM-001", expiry_offset_days=100)
        b2 = _batch("B2", state=BatchState.RELEASED, raw_lot="RM-001", expiry_offset_days=100)
        b3 = _batch("B3", state=BatchState.RELEASED, raw_lot="RM-002", expiry_offset_days=100)  # diff lot

        record = re.cascade_recall([b1, b2, b3], "B1", "RM-001", "Critical defect", BASE)
        recalled_ids = set(record.recalled_batch_ids)
        assert "B1" in recalled_ids
        assert "B2" in recalled_ids
        assert "B3" not in recalled_ids

    def test_ec9_expired_batch_excluded_from_cascade(self):
        """EC-9: Recall cascade excludes expired batches."""
        re = RecallEngine()
        # B-FRESH: not expired
        b_fresh = _batch("B-FRESH", state=BatchState.RELEASED, raw_lot="RM-001", expiry_offset_days=100)
        # B-EXP: expired (expiry_date in the past)
        b_exp = _batch("B-EXP", state=BatchState.RELEASED, raw_lot="RM-001", expiry_offset_days=-1)
        b_exp.expiry_date = BASE - timedelta(days=1)  # already expired

        # Recall at BASE (after expiry of B-EXP)
        record = re.cascade_recall(
            [b_fresh, b_exp], "B-FRESH", "RM-001", "Critical defect", BASE
        )
        # B-FRESH should be recalled; B-EXP should NOT (expired)
        assert "B-FRESH" in record.recalled_batch_ids
        assert "B-EXP" not in record.recalled_batch_ids

    def test_already_recalled_batch_not_double_counted(self):
        """Already-recalled batches should not cause duplicate IDs."""
        re = RecallEngine()
        b1 = _batch("B1", state=BatchState.RECALLED, raw_lot="RM-001")
        b2 = _batch("B2", state=BatchState.RELEASED, raw_lot="RM-001")

        record = re.cascade_recall([b1, b2], "B2", "RM-001", "Test", BASE)
        # B2 should be recalled; B1 is already terminal
        assert "B2" in record.recalled_batch_ids

    def test_recall_rule_id_is_br09(self):
        re = RecallEngine()
        b = _batch("B1", state=BatchState.RELEASED, raw_lot="RM-X")
        record = re.cascade_recall([b], "B1", "RM-X", "Test", BASE)
        assert record.rule_id == "BR-09"

    def test_check_on_hold_critical_detects_critical(self):
        re = RecallEngine()
        result = InspectionResult(
            batch_id="B1",
            sample_size=50,
            defects={DefectClass.CRITICAL: 1, DefectClass.MAJOR: 0, DefectClass.MINOR: 0},
            sampled_at=BASE,
            recorded_at=BASE,
        )
        assert re.check_on_hold_critical(result) is True

    def test_check_on_hold_critical_no_critical(self):
        re = RecallEngine()
        result = InspectionResult(
            batch_id="B1",
            sample_size=50,
            defects={DefectClass.CRITICAL: 0, DefectClass.MAJOR: 2, DefectClass.MINOR: 0},
            sampled_at=BASE,
            recorded_at=BASE,
        )
        assert re.check_on_hold_critical(result) is False

