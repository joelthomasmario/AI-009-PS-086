"""
test_lifecycle.py – Tests for batch lifecycle state transitions (Section 6).

Joseph Mangaly (2463031)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from datetime import datetime

from src.models import Batch, BatchState, LEGAL_TRANSITIONS

BASE = datetime(2026, 1, 15, 10, 0, 0)


def _fresh_batch(batch_id="BL-001"):
    return Batch(
        batch_id=batch_id, product_id="P001",
        source_id="S001", source_type="SUPPLIER",
        lot_size=100, raw_material_lot_id="RM-001",
        manufacture_date=BASE,
    )


class TestLegalTransitions:
    """Section 6: Legal batch lifecycle state transitions."""

    def test_quarantine_to_under_inspection(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        assert b.state == BatchState.UNDER_INSPECTION

    def test_under_inspection_to_released(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        assert b.state == BatchState.RELEASED

    def test_under_inspection_to_rejected(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.REJECTED, "failed", BASE)
        assert b.state == BatchState.REJECTED

    def test_released_to_on_hold(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE)
        assert b.state == BatchState.ON_HOLD

    def test_released_to_recalled(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        b.transition_to(BatchState.RECALLED, "recall", BASE)
        assert b.state == BatchState.RECALLED

    def test_on_hold_to_released(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE)
        b.transition_to(BatchState.RELEASED, "cleared", BASE)
        assert b.state == BatchState.RELEASED

    def test_on_hold_to_rejected(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE)
        b.transition_to(BatchState.REJECTED, "fail", BASE)
        assert b.state == BatchState.REJECTED

    def test_on_hold_to_recalled(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        b.transition_to(BatchState.ON_HOLD, "hold", BASE)
        b.transition_to(BatchState.RECALLED, "recall", BASE)
        assert b.state == BatchState.RECALLED

    def test_rejected_to_rework(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.REJECTED, "fail", BASE)
        b.transition_to(BatchState.REWORK, "rework", BASE)
        assert b.state == BatchState.REWORK

    def test_rework_to_under_inspection(self):
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.REJECTED, "fail", BASE)
        b.transition_to(BatchState.REWORK, "rework", BASE)
        b.transition_to(BatchState.UNDER_INSPECTION, "reinspect", BASE)
        assert b.state == BatchState.UNDER_INSPECTION

    def test_recalled_is_terminal(self):
        """RECALLED must be a terminal state – no transitions allowed from it."""
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        b.transition_to(BatchState.RECALLED, "recall", BASE)
        assert b.state == BatchState.RECALLED
        # Any further transition should raise ValueError
        with pytest.raises(ValueError, match="Illegal transition"):
            b.transition_to(BatchState.RELEASED, "attempt", BASE)


class TestIllegalTransitions:
    """Verify that illegal transitions raise ValueError."""

    @pytest.mark.parametrize("from_state,illegal_target", [
        (BatchState.QUARANTINE,       BatchState.RELEASED),
        (BatchState.QUARANTINE,       BatchState.REJECTED),
        (BatchState.QUARANTINE,       BatchState.RECALLED),
        (BatchState.UNDER_INSPECTION, BatchState.REWORK),
        (BatchState.UNDER_INSPECTION, BatchState.RECALLED),
        (BatchState.RELEASED,         BatchState.REJECTED),
        (BatchState.RELEASED,         BatchState.REWORK),
        (BatchState.REJECTED,         BatchState.RELEASED),
        (BatchState.REJECTED,         BatchState.RECALLED),
        (BatchState.RECALLED,         BatchState.RELEASED),
    ])
    def test_illegal_transition_raises(self, from_state, illegal_target):
        b = _fresh_batch()
        # Manually set state to bypass normal flow
        b.state = from_state
        with pytest.raises(ValueError, match="Illegal transition"):
            b.transition_to(illegal_target, "illegal", BASE)

    def test_state_history_is_recorded(self):
        """State history records every transition."""
        b = _fresh_batch()
        b.transition_to(BatchState.UNDER_INSPECTION, "start", BASE)
        b.transition_to(BatchState.RELEASED, "accepted", BASE)
        states_in_history = [h[0] for h in b.state_history]
        assert BatchState.QUARANTINE in states_in_history
        assert BatchState.UNDER_INSPECTION in states_in_history
        assert BatchState.RELEASED in states_in_history

