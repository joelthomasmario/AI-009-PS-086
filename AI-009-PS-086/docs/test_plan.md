# Test Plan

**Project:** AI-009 | PS-086 | Section 6BTAI

---

## Test Execution Results (Actual)

**Run Date:** 2026-11-05  
**Python Version:** 3.13.5  
**pytest Version:** 9.2.0  
**Result:** ✅ **144 passed, 0 failed**

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0
collected 144 items

...144 passed in 0.75s...
```

---

## Test Files

| File | Tests | Coverage Area |
|------|-------|---------------|
| `test_br01_sampling_plan.py` | 15 | Code letters, CSV loader, lookup |
| `test_br02_defect_classification.py` | 9 | Defect classes, AQL defaults, Ac/Re |
| `test_br03_sample_size.py` | 5 | 100% inspection trigger |
| `test_br04_switching.py` | 13 | NORMAL↔TIGHTENED, DISCONTINUED, REDUCED |
| `test_br05_reduced.py` | 5 | REDUCED→NORMAL triggers |
| `test_br06_discontinued.py` | 5 | Discontinued state, corrective action |
| `test_br07_rework.py` | 9 | Rework eligibility, lifecycle |
| `test_br08_hold.py` | 13 | Hold window, cascade, double sample |
| `test_br09_recall.py` | 5 | Recall cascade, expiry exclusion |
| `test_br10_shelf_life.py` | 5 | Shelf-life ratios, rejection reasons |
| `test_br11_late_results.py` | 6 | 48-hour window, switching interaction |
| `test_lifecycle.py` | 22 | Legal transitions, illegal transitions |
| `test_integration.py` | 12 | End-to-end workflows, reports |

---

## Edge Case Test Map

| EC | Description | Test Method | File | Result |
|----|-------------|-------------|------|--------|
| EC-1a | Lot = 280 → code G | `test_lot_size_to_code_letter[280-G]` | BR01 | ✅ |
| EC-1b | Lot = 281 → code H | `test_lot_size_to_code_letter[281-H]` | BR01 | ✅ |
| EC-2 | Defects = Ac → ACCEPTED | `test_ec2_defects_exactly_equal_to_ac` | BR02 | ✅ |
| EC-3 | Defects = Re → REJECTED | `test_ec3_defects_exactly_equal_to_re` | BR02 | ✅ |
| EC-4 | Between Ac and Re under REDUCED | `test_ec4_between_ac_and_re_accepted_switches_to_normal` | BR05 | ✅ |
| EC-5 | 2nd rejection; 1st is 5th-previous | `test_ec5_first_rejection_exactly_fifth_previous` | BR04 | ✅ |
| EC-6 | Major = 2×Re → rework eligible | `test_ec6_major_exactly_2_re_eligible` | BR07 | ✅ |
| EC-7 | Hold exactly 30 days → allowed | `test_ec7_hold_exactly_30_days_allowed` | BR08 | ✅ |
| EC-8 | Hold 31 days → rejected | `test_ec8_hold_31_days_after_release_rejected` | BR08 | ✅ |
| EC-9 | Recall cascade excludes expired | `test_ec9_expired_batch_excluded_from_cascade` | BR09 | ✅ |
| EC-10 | Exactly 48h → NOT late | `test_exactly_48_hours_is_not_late` | BR11 | ✅ |

---

## Additional Error-Condition Tests

| Condition | Test Method | File | Result |
|-----------|-------------|------|--------|
| Invalid command | `test_invalid_command_returns_failure` | Integration | ✅ |
| Missing CSV entries | `test_lookup_missing_entry_raises` | BR01 | ✅ |
| Duplicate product ID | `test_duplicate_product_id_fails` | Integration | ✅ |
| Illegal state transitions (10 cases) | `test_illegal_transition_raises[*]` | Lifecycle | ✅ |
| Missing corrective action (DISCONTINUED) | `test_inspection_blocked_when_discontinued` | BR06 | ✅ |
| Malformed CSV row | `test_malformed_csv_raises_value_error` | BR01 | ✅ |
| Missing CSV column | `test_missing_required_column_raises` | BR01 | ✅ |
| Rework on non-rejected batch | `test_non_rejected_batch_raises` | BR07 | ✅ |
| Hold on non-released batch | `test_non_released_batch_cannot_be_held` | BR08 | ✅ |
| Second rework attempt | `test_second_rejection_is_final` | BR07 | ✅ |

---

## Running Tests

```bash
# Full suite
python -m pytest tests/ -v

# Single file
python -m pytest tests/test_br04_switching.py -v

# Specific test
python -m pytest tests/test_br08_hold.py::TestHoldEligibility::test_ec7_hold_exactly_30_days_allowed -v

# With coverage (requires pytest-cov)
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

