# AQL Sampling, Inspection Severity and Batch Release Engine

**Project ID:** AI-009 | **Problem Statement:** PS-086  
**Section:** 6BTAI  

| # | Member | Roll No | Ownership |
|---|--------|---------|-----------|
| 1 | Joel Thomas Mario J | 2463029 | AQL sampling engine, inspection calculations, defect evaluation |
| 2 | Joselet K Jaison | 2463030 | Supplier/line switching engine |
| 3 | Joseph Mangaly | 2463031 | Batch lifecycle, rework, hold, release, recall |

---

## 1. Project Overview

This system is an ISO 2859-1–based AQL quality inspection engine used by manufacturing companies to determine whether incoming or production batches should be **accepted, rejected, reworked, held, released or recalled**.

---

## 2. Installation

### Requirements
- Python 3.10 or higher
- `pytest` (for testing)

### Setup
```bash
# Clone or unzip the project
cd AI-009-PS-086

# Install in development mode (no external dependencies required)
pip install -e .

# Install testing extras
pip install pytest
```

---

## 3. Running the Project

```bash
python -m src.main \
  --commands   commands/example_commands.csv \
  --sampling-plan data/sampling_plan.csv \
  --output     outputs/ \
  --verbose
```

### Arguments

| Argument | Short | Description | Required |
|----------|-------|-------------|----------|
| `--commands` | `-c` | Path to command CSV file | ✅ |
| `--sampling-plan` | `-s` | Path to AQL sampling plan CSV | ✅ |
| `--output` | `-o` | Output directory (default: `outputs/`) | No |
| `--verbose` | `-v` | Print every command result to stdout | No |

---

## 4. Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_br01_sampling_plan.py -v

# Run with coverage (if pytest-cov is installed)
python -m pytest tests/ --cov=src --cov-report=term-missing
```

**Test results (actual execution):** 144 tests passed, 0 failed.

---

## 5. Command File Format

### File Format
A UTF-8 CSV file. First column is always `command`. Remaining columns carry command-specific parameters. Unused columns in a row should be left empty.

### Shared Header (all commands use this 24-column header)

Every command file must start with this header row. Columns not needed by a particular command are left empty.

```
command,product_id,name,total_shelf_life_days,supplier_id,line_id,batch_id,
source_id,source_type,lot_size,raw_material_lot_id,manufacture_date,expiry_date,
critical,major,minor,sampled_at,recorded_at,rework_round,reason,action_id,
description,complaint_id,timestamp
```

> **Column index quick-reference**
>
> | # | Column | Used by |
> |---|--------|---------|
> | 0 | `command` | All |
> | 1 | `product_id` | REGISTER_PRODUCT, CREATE_BATCH |
> | 2 | `name` | REGISTER_PRODUCT, REGISTER_SUPPLIER, REGISTER_LINE |
> | 3 | `total_shelf_life_days` | REGISTER_PRODUCT |
> | 4 | `supplier_id` | REGISTER_SUPPLIER |
> | 5 | `line_id` | REGISTER_LINE |
> | 6 | `batch_id` | CREATE_BATCH, BEGIN_INSPECTION, RECORD_RESULT, REWORK, RELEASE, HOLD, COMPLAINT, RECALL |
> | 7 | `source_id` | CREATE_BATCH, CORRECTIVE_ACTION |
> | 8 | `source_type` | CREATE_BATCH (`SUPPLIER` or `LINE`) |
> | 9 | `lot_size` | CREATE_BATCH |
> | 10 | `raw_material_lot_id` | CREATE_BATCH |
> | 11 | `manufacture_date` | CREATE_BATCH |
> | 12 | `expiry_date` | CREATE_BATCH |
> | 13 | `critical` | RECORD_RESULT |
> | 14 | `major` | RECORD_RESULT |
> | 15 | `minor` | RECORD_RESULT |
> | 16 | `sampled_at` | RECORD_RESULT |
> | 17 | `recorded_at` | RECORD_RESULT |
> | 18 | `rework_round` | RECORD_RESULT (`0`=original, `1`=rework) |
> | 19 | `reason` | HOLD, RECALL |
> | 20 | `action_id` | CORRECTIVE_ACTION |
> | 21 | `description` | CORRECTIVE_ACTION, COMPLAINT |
> | 22 | `complaint_id` | COMPLAINT |
> | 23 | `timestamp` | BEGIN_INSPECTION, REWORK, RELEASE, HOLD, CORRECTIVE_ACTION, COMPLAINT, RECALL |

### Commands

#### `REGISTER_PRODUCT`
Register a new product with its AQL configuration.

| Field | Required | Description |
|-------|----------|-------------|
| `product_id` | ✅ | Unique product identifier |
| `name` | ✅ | Product name |
| `total_shelf_life_days` | No | Total shelf life in days (0 = no check) |

```csv
command,product_id,name,total_shelf_life_days
REGISTER_PRODUCT,P001,Industrial Valve Type A,365
```

#### `REGISTER_SUPPLIER`
Register a supplier.

| Field | Required | Description |
|-------|----------|-------------|
| `supplier_id` | ✅ | Unique supplier identifier |
| `name` | ✅ | Supplier name |

```csv
command,supplier_id,name
REGISTER_SUPPLIER,S001,Acme Components Ltd
```

#### `REGISTER_LINE`
Register a production line.

| Field | Required | Description |
|-------|----------|-------------|
| `line_id` | ✅ | Unique line identifier |
| `name` | ✅ | Line name |

#### `CREATE_BATCH`
Create a new batch in QUARANTINE state.

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Unique batch identifier |
| `product_id` | ✅ | Associated product |
| `source_id` | ✅ | Supplier or line ID |
| `source_type` | ✅ | `SUPPLIER` or `LINE` |
| `lot_size` | ✅ | Total units in the lot |
| `raw_material_lot_id` | ✅ | Raw material lot (for hold/recall cascade) |
| `manufacture_date` | ✅ | Format: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` |
| `expiry_date` | No | Format: `YYYY-MM-DD` |

#### `BEGIN_INSPECTION`
Move batch from QUARANTINE to UNDER_INSPECTION.

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Batch to inspect |
| `timestamp` | No | Inspection start time |

#### `RECORD_RESULT`
Record inspection defect counts and generate a decision.

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Batch being inspected |
| `critical` | ✅ | Critical defect count |
| `major` | ✅ | Major defect count |
| `minor` | ✅ | Minor defect count |
| `sampled_at` | ✅ | When sampling was performed |
| `recorded_at` | No | When result was entered (defaults to now) |
| `rework_round` | No | `0` = original, `1` = rework reinspection |

#### `REWORK`
Initiate rework on an eligible rejected batch (BR-07).

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Batch in REJECTED state |
| `timestamp` | No | Rework start time |

#### `RELEASE`
Manually release a batch (enforces shelf-life check, BR-10).

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Batch to release |
| `timestamp` | No | Release time |

#### `HOLD`
Place a released batch ON_HOLD (BR-08).

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Batch to hold |
| `reason` | ✅ | Hold reason |
| `timestamp` | No | Hold time |

#### `CORRECTIVE_ACTION`
Register corrective action on a DISCONTINUED source (BR-06).

| Field | Required | Description |
|-------|----------|-------------|
| `action_id` | ✅ | Unique action ID |
| `source_id` | ✅ | Supplier or line ID |
| `description` | ✅ | Description of corrective action |
| `timestamp` | No | Registration time |

#### `COMPLAINT`
File a customer complaint to trigger recall (BR-09).

| Field | Required | Description |
|-------|----------|-------------|
| `complaint_id` | ✅ | Unique complaint ID |
| `batch_id` | ✅ | Cited batch ID |
| `description` | ✅ | Complaint description |
| `timestamp` | No | Filing time |

#### `RECALL`
Directly trigger a recall and cascade (BR-09).

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | ✅ | Trigger batch ID |
| `reason` | ✅ | Recall reason |
| `timestamp` | No | Recall time |

---

## 6. Example Command File

```csv
command,product_id,name,total_shelf_life_days,supplier_id,line_id,batch_id,source_id,source_type,lot_size,raw_material_lot_id,manufacture_date,expiry_date,critical,major,minor,sampled_at,recorded_at,rework_round,reason,action_id,description,complaint_id,timestamp
REGISTER_PRODUCT,P001,Widget Alpha,365,,,,,,,,,,,,,,,,,,,,,
REGISTER_SUPPLIER,,Acme Corp,,S001,,,,,,,,,,,,,,,,,,,,
CREATE_BATCH,P001,,,S001,,B001,S001,SUPPLIER,200,RM-001,2026-01-01,2026-12-31,,,,,,,,,,,
BEGIN_INSPECTION,,,,,,B001,,,,,,,,,,,,,,,,,2026-01-15T08:00:00
RECORD_RESULT,,,,,,B001,,,,,,,0,0,2,2026-01-15T08:00:00,2026-01-15T09:00:00,0,,,,,,
HOLD,,,,,,B001,,,,,,,,,,,,,Supplier related batch rejected,,,,2026-02-05T10:00:00
```

> **Key rule:** `timestamp` (column 23) is the explicit override time for `BEGIN_INSPECTION`, `REWORK`, `RELEASE`, `HOLD`, `CORRECTIVE_ACTION`, `COMPLAINT`, and `RECALL`. Leave it empty to use the system clock; always populate it in test command files for deterministic replay.

See `commands/example_commands.csv` and `commands/rework_example.csv` for complete working examples.

---

## 7. Sample Output

The following are **actual outputs** from running `commands/example_commands.csv`.

### `outputs/batch_decisions.csv`
```
decision_id,batch_id,product_id,source_id,lot_size,code_letter,severity,sample_size,defects_critical,defects_major,defects_minor,ac_critical,ac_major,ac_minor,re_critical,re_major,re_minor,decision,decision_reason,rule_ids,sampled_at,recorded_at,is_late
7cd64de4...,B001,P001,S001,250,G,NORMAL,32,0,1,2,0,1,2,1,2,3,ACCEPTED,All defect classes within acceptance limits,BR-01|BR-02,2026-01-10T08:00:00,2026-01-10T09:00:00,False
aa43119b...,B002,P001,S001,300,H,NORMAL,50,0,0,1,0,2,3,1,3,4,ACCEPTED,All defect classes within acceptance limits,BR-01|BR-02,2026-01-11T08:00:00,2026-01-11T09:00:00,False
30df4de0...,B003,P001,S001,280,G,NORMAL,32,0,2,3,0,1,2,1,2,3,REJECTED,MAJOR defects=2 >= Re=2; MINOR defects=3 >= Re=3,BR-01|BR-02,2026-01-12T08:00:00,2026-01-12T09:00:00,False
63f8afc0...,B004,P001,S001,320,H,NORMAL,50,0,3,0,0,2,3,1,3,4,REJECTED,MAJOR defects=3 >= Re=3,BR-01|BR-02,2026-01-20T08:00:00,2026-01-20T09:30:00,False
184e74dd...,B005,P002,S002,500,H,NORMAL,50,1,0,0,0,2,3,1,3,4,REJECTED_CRITICAL,CRITICAL defect count=1 (>=1 triggers rejection per BR-02),BR-01|BR-02,2026-01-25T08:00:00,2026-01-25T09:00:00,False
```

### `outputs/switching_history.csv`
```
record_id,source_id,previous_severity,new_severity,triggering_batch_id,rule_id,event,timestamp
74b3c4ae...,S001,NORMAL,TIGHTENED,B004,BR-04,2 rejections in last 4 batches,2026-01-20T08:00:00
```

### `outputs/release_register.csv`
```
batch_id,product_id,source_id,lot_size,raw_material_lot_id,manufacture_date,expiry_date,released_at,current_state
B001,P001,S001,250,RM-2024-001,2026-01-01T00:00:00,2026-12-31T00:00:00,2026-01-10T09:00:00,ON_HOLD
B002,P001,S001,300,RM-2024-001,2026-01-05T00:00:00,2027-01-05T00:00:00,2026-01-11T09:00:00,RELEASED
```

### `outputs/recall_register.csv`
```
recall_id,trigger_batch_id,recalled_batch_ids,reason,rule_id,recalled_at
(empty – no recalls triggered in this scenario)
```

---

## 8. Implemented Business-Rule Checklist

| Rule | Description | Status |
|------|-------------|--------|
| BR-01 | Sampling plan lookup from CSV; code-letter bands; no invented values | ✅ |
| BR-02 | Defect classification; default AQLs; critical ≥1 always rejects | ✅ |
| BR-03 | 100% inspection when sample size ≥ lot size | ✅ |
| BR-04 | NORMAL↔TIGHTENED switching; TIGHTENED→DISCONTINUED | ✅ |
| BR-05 | REDUCED switching (rejection, between-Ac-and-Re, irregularity) | ✅ |
| BR-06 | DISCONTINUED blocks inspection; corrective action resumes at TIGHTENED | ✅ |
| BR-07 | Rework eligibility; reinspect at TIGHTENED; second rejection is final | ✅ |
| BR-08 | Hold within 30 days; double sample; cascade from related batch | ✅ |
| BR-09 | Recall on critical/complaint; cascade excludes expired batches | ✅ |
| BR-10 | Shelf-life check: reject if remaining < 75% | ✅ |
| BR-11 | LATE flag if recorded > 48h; excluded from NORMAL→REDUCED switching | ✅ |

### Edge Cases Tested

| EC | Description | Test | Status |
|----|-------------|------|--------|
| EC-1 | Lot size exactly 280 vs 281 | `test_lot_size_to_code_letter` | ✅ |
| EC-2 | Defects exactly equal to Ac | `test_ec2_defects_exactly_equal_to_ac` | ✅ |
| EC-3 | Defects exactly equal to Re | `test_ec3_defects_exactly_equal_to_re` | ✅ |
| EC-4 | Between-Ac-and-Re under REDUCED | `test_ec4_between_ac_and_re_accepted_switches_to_normal` | ✅ |
| EC-5 | 2nd rejection when 1st is exactly 5th-previous | `test_ec5_first_rejection_exactly_fifth_previous` | ✅ |
| EC-6 | Major defects exactly 2×Re | `test_ec6_major_exactly_2_re_eligible` | ✅ |
| EC-7 | Hold exactly 30 days after release | `test_ec7_hold_exactly_30_days_allowed` | ✅ |
| EC-8 | Hold 31 days after release | `test_ec8_hold_31_days_after_release_rejected` | ✅ |
| EC-9 | Recall cascade excludes expired batch | `test_ec9_expired_batch_excluded_from_cascade` | ✅ |
| EC-10 | Result recorded exactly 48h after sampling | `test_exactly_48_hours_is_not_late` | ✅ |

---

## 9. Project Structure

```
AI-009-PS-086/
├── src/
│   ├── __init__.py
│   ├── models.py              # Core data models (all members)
│   ├── sampling_engine.py     # BR-01, BR-02, BR-03 (Joel)
│   ├── switching_engine.py    # BR-04, BR-05, BR-06 (Joselet)
│   ├── lifecycle_engine.py    # BR-10, BR-11 (Joseph)
│   ├── rework_engine.py       # BR-07 (Joseph)
│   ├── hold_engine.py         # BR-08 (Joseph)
│   ├── recall_engine.py       # BR-09 (Joseph)
│   ├── inspection_engine.py   # Orchestration (shared)
│   ├── product_service.py     # Product registration (Joel)
│   ├── supplier_service.py    # Supplier/line registration (Joselet)
│   ├── command_parser.py      # CSV command dispatch (shared)
│   ├── validation.py          # Input validation (shared)
│   ├── report_generator.py    # 5 report outputs (shared)
│   └── main.py                # CLI entry point (shared)
├── tests/
│   ├── conftest.py
│   ├── test_br01_sampling_plan.py
│   ├── test_br02_defect_classification.py
│   ├── test_br03_sample_size.py
│   ├── test_br04_switching.py
│   ├── test_br05_reduced.py
│   ├── test_br06_discontinued.py
│   ├── test_br07_rework.py
│   ├── test_br08_hold.py
│   ├── test_br09_recall.py
│   ├── test_br10_shelf_life.py
│   ├── test_br11_late_results.py
│   ├── test_lifecycle.py
│   └── test_integration.py
├── data/
│   └── sampling_plan.csv      # AQL sampling plan (required)
├── commands/
│   ├── example_commands.csv
│   └── rework_example.csv
├── outputs/                   # Generated reports go here
├── docs/
│   ├── design_document.md
│   ├── business_rules.md
│   ├── architecture.md
│   ├── decision_log.md
│   └── test_plan.md
├── README.md
├── setup.py
└── pytest.ini
```

---

## 10. Remaining Assumptions / Ambiguities

1. **BR-04 "within five consecutive batches"** – Interpreted as a sliding window of the last 5 batches for the same source. If a source has fewer than 5 batches, the window is smaller.
2. **BR-05 "total defects within the reduced-limit column"** – Interpreted as: total defects across all classes ≤ Ac of the REDUCED plan for the MAJOR AQL.
3. **BR-10 "remaining shelf life < 75%"** – The check uses `remaining_days / total_shelf_life_days`. Exactly 75% is **allowed** (consistent with ≥ 75% required).
4. **BR-11 "exactly 48 hours"** – Interpreted as: `recorded_at - sampled_at > 48h` triggers LATE. Exactly 48h is **not** late.
5. **Sampling plan CSV** – The supplied `data/sampling_plan.csv` uses standard ISO 2859-1 Level II values. If official form-specific values differ, replace this file — the system reads from it without hardcoding.
6. **Rework reinspection severity** – Always TIGHTENED per BR-07, regardless of the supplier's current severity at time of reinspection.
7. **DISCONTINUED source with corrective action** – The `corrective_action_registered` flag is set per source, not per batch. After one corrective action, all future inspections proceed at TIGHTENED.

---

## 11. Individual Viva Preparation Notes

### Joel Thomas Mario J (2463029) – Sampling Engine
**Key files:** `src/sampling_engine.py`, `src/product_service.py`, `src/models.py` (sampling/defect parts)

Prepare to explain:
- How ISO 2859-1 lot-size bands map to code letters (BR-01).
- The `SamplingPlanLoader` class: how it reads and indexes the CSV, and why `KeyError` is raised for missing entries (never invent values).
- The `SamplingEngine.evaluate()` method: per-class AQL lookup, critical auto-reject logic (BR-02), 100% inspection trigger (BR-03).
- Why `PerClassEvaluation` and `SamplingDecision` are separate dataclasses.
- The `evaluate_reduced_between()` method: detecting between-Ac-and-Re results.
- Edge cases EC-1 (280 vs 281), EC-2 (Ac), EC-3 (Re).

### Joselet K Jaison (2463030) – Switching Engine
**Key files:** `src/switching_engine.py`, `src/supplier_service.py`, `src/models.py` (Supplier/ProductionLine)

Prepare to explain:
- The severity state machine: NORMAL ↔ TIGHTENED → DISCONTINUED; NORMAL → REDUCED.
- How the sliding 5-batch window (`recent_decisions` list) works for BR-04.
- The difference between `consecutive_accepts` and `tightened_reject_count`.
- Why LATE results don't count toward NORMAL→REDUCED (BR-11 interaction with BR-04).
- Production irregularity detection: gap > 30 days (BR-05).
- The `apply_corrective_action()` method: validates DISCONTINUED state, switches to TIGHTENED.
- Edge cases EC-4 (between-Ac-Re), EC-5 (5th-previous rejection).

### Joseph Mangaly (2463031) – Lifecycle Engine
**Key files:** `src/lifecycle_engine.py`, `src/rework_engine.py`, `src/hold_engine.py`, `src/recall_engine.py`, `src/models.py` (Batch)

Prepare to explain:
- The `LEGAL_TRANSITIONS` dict and how `Batch.transition_to()` enforces it.
- Shelf-life ratio calculation and the 75% threshold (BR-10).
- Rework eligibility: critical=0, major ≤ 2×Re, rework_count < 1 (BR-07).
- Hold window: 30 days from `released_at`; exactly 30 days is allowed (EC-7, EC-8).
- Recall cascade: filters by `raw_material_lot_id`, excludes expired batches (EC-9), excludes already-recalled batches.
- Why `RECALLED` is a terminal state (empty allowed-transitions list).
- The `state_history` list and its use for audit trails.

