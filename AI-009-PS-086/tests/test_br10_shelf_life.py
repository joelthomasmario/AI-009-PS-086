"""
test_br10_shelf_life.py – Tests for BR-10: Shelf-life check on release.

Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from src.lifecycle_engine import LifecycleEngine
from src.models import Batch, BatchState, DecisionCode

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _batch_under_inspection(
    batch_id="B-SL",
    total_shelf_life_days=100,
    expiry_offset_days=100,
):
    b = Batch(
        batch_id=batch_id, product_id="P001",
        source_id="S001", source_type="SUPPLIER",
        lot_size=100, raw_material_lot_id="RM-001",
        manufacture_date=BASE - timedelta(days=expiry_offset_days - total_shelf_life_days),
        expiry_date=BASE + timedelta(days=expiry_offset_days),
        total_shelf_life_days=total_shelf_life_days,
    )
    b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)
    return b


class TestShelfLife:
    """BR-10: Batch cannot be released if remaining shelf life < 75%."""

    def test_adequate_shelf_life_allows_release(self):
        """75% or more remaining → release allowed."""
        lc = LifecycleEngine()
        # 100 total days, 76 remaining → 76% ≥ 75% → release OK
        b = _batch_under_inspection(total_shelf_life_days=100, expiry_offset_days=76)
        success, code, reason = lc.try_release(b, as_of=BASE)
        assert success is True
        assert b.state == BatchState.RELEASED

    def test_exactly_75_pct_allows_release(self):
        """Exactly 75% remaining → release allowed (boundary at 75%)."""
        lc = LifecycleEngine()
        # 100 total days, 75 remaining → exactly 75%
        b = _batch_under_inspection(total_shelf_life_days=100, expiry_offset_days=75)
        success, code, reason = lc.try_release(b, as_of=BASE)
        assert success is True, f"Expected release at exactly 75%, got: {reason}"

    def test_below_75_pct_rejected_short_dated(self):
        """Less than 75% remaining → rejected with SHORT_DATED."""
        lc = LifecycleEngine()
        # 100 total days, 74 remaining → 74% < 75% → SHORT_DATED
        b = _batch_under_inspection(total_shelf_life_days=100, expiry_offset_days=74)
        success, code, reason = lc.try_release(b, as_of=BASE)
        assert success is False
        assert b.state == BatchState.REJECTED
        assert b.is_short_dated is True
        assert b.rejection_reason == "SHORT_DATED"
        assert code == DecisionCode.REJECTED_SHORT_DATED.value

    def test_no_shelf_life_configured_always_releases(self):
        """Product without shelf-life setting → always release."""
        lc = LifecycleEngine()
        b = Batch(
            batch_id="B-NO-SL", product_id="P001",
            source_id="S001", source_type="SUPPLIER",
            lot_size=100, raw_material_lot_id="RM-001",
            manufacture_date=BASE,
            expiry_date=None,
            total_shelf_life_days=0,  # no check
        )
        b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)
        success, code, reason = lc.try_release(b, as_of=BASE)
        assert success is True

    def test_no_expiry_date_always_releases(self):
        """Batch without expiry_date → no shelf-life check → always release."""
        lc = LifecycleEngine()
        b = Batch(
            batch_id="B-NO-EXP", product_id="P001",
            source_id="S001", source_type="SUPPLIER",
            lot_size=100, raw_material_lot_id="RM-001",
            manufacture_date=BASE,
            expiry_date=None,
            total_shelf_life_days=100,  # has shelf life days but no expiry date
        )
        b.transition_to(BatchState.UNDER_INSPECTION, "test", BASE)
        success, code, reason = lc.try_release(b, as_of=BASE)
        assert success is True

