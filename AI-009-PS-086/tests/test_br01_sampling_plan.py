"""
test_br01_sampling_plan.py – Tests for BR-01: Sampling plan lookup.

Joel Thomas Mario J (2463029)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import pytest
from src.sampling_engine import SamplingPlanLoader, get_code_letter
from src.models import InspectionSeverity


# ---------------------------------------------------------------------------
# Code letter assignment (BR-01)
# ---------------------------------------------------------------------------

class TestCodeLetterBands:
    """Verify lot-size to code-letter mapping (BR-01)."""

    @pytest.mark.parametrize("lot_size,expected", [
        (2,     "A"),
        (8,     "A"),
        (9,     "B"),
        (15,    "B"),
        (16,    "C"),
        (25,    "C"),
        (26,    "D"),
        (50,    "D"),
        (51,    "E"),
        (90,    "E"),
        (91,    "F"),
        (150,   "F"),
        (151,   "G"),
        (280,   "G"),   # Edge case EC-1a: exactly 280
        (281,   "H"),   # Edge case EC-1b: exactly 281
        (500,   "H"),
        (501,   "J"),
        (1200,  "J"),
        (1201,  "K"),
        (3200,  "K"),
        (3201,  "L"),
        (10000, "L"),
    ])
    def test_lot_size_to_code_letter(self, lot_size, expected):
        assert get_code_letter(lot_size) == expected

    def test_lot_size_below_minimum_raises(self):
        with pytest.raises(ValueError, match="below the minimum"):
            get_code_letter(1)

    def test_lot_size_above_maximum_raises(self):
        with pytest.raises(ValueError, match="exceeds the maximum"):
            get_code_letter(10001)

    def test_lot_size_zero_raises(self):
        with pytest.raises(ValueError):
            get_code_letter(0)


# ---------------------------------------------------------------------------
# Sampling plan loader (BR-01)
# ---------------------------------------------------------------------------

class TestSamplingPlanLoader:
    """Verify that the sampling plan CSV is loaded correctly."""

    def test_loader_loads_entries(self, plan_loader):
        assert len(plan_loader.entries) > 0

    def test_lookup_valid_entry(self, plan_loader):
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
        assert entry.code_letter == "G"
        assert entry.aql == 1.0
        assert entry.severity == InspectionSeverity.NORMAL
        assert entry.sample_size > 0
        assert entry.re > entry.ac

    def test_lookup_missing_entry_raises(self, plan_loader):
        """BR-01: Missing values must not be invented – KeyError expected."""
        with pytest.raises(KeyError, match="No sampling plan entry"):
            plan_loader.lookup("Z", 999.0, InspectionSeverity.NORMAL)

    def test_lookup_tightened_severity(self, plan_loader):
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.TIGHTENED)
        assert entry.severity == InspectionSeverity.TIGHTENED

    def test_lookup_reduced_severity(self, plan_loader):
        entry = plan_loader.lookup("G", 1.0, InspectionSeverity.REDUCED)
        assert entry.severity == InspectionSeverity.REDUCED

    def test_all_three_severities_for_every_letter(self, plan_loader):
        """Every code letter should have NORMAL, TIGHTENED, and REDUCED entries."""
        letters = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L"]
        aql = 1.0
        for letter in letters:
            for sev in [InspectionSeverity.NORMAL, InspectionSeverity.TIGHTENED, InspectionSeverity.REDUCED]:
                entry = plan_loader.lookup(letter, aql, sev)
                assert entry is not None, f"Missing entry for {letter}/{aql}/{sev}"

    def test_re_always_greater_than_ac(self, plan_loader):
        for entry in plan_loader.entries:
            assert entry.re > entry.ac, (
                f"Re ({entry.re}) must be > Ac ({entry.ac}) for "
                f"letter={entry.code_letter}, aql={entry.aql}, sev={entry.severity}"
            )

    def test_missing_csv_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SamplingPlanLoader(str(tmp_path / "nonexistent.csv"))

    def test_malformed_csv_raises_value_error(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("code_letter,aql\nA,notanumber\n")
        with pytest.raises(ValueError):
            SamplingPlanLoader(str(bad_csv))

    def test_missing_required_column_raises(self, tmp_path):
        bad_csv = tmp_path / "missing_col.csv"
        bad_csv.write_text("code_letter,aql,severity,sample_size\nA,1.0,NORMAL,2\n")
        with pytest.raises(ValueError, match="missing required columns"):
            SamplingPlanLoader(str(bad_csv))

