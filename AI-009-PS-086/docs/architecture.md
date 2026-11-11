# System Architecture

**Project:** AI-009 | PS-086 | Section 6BTAI

---

## Module Dependency Graph

```
main.py
  └── command_parser.py
        ├── inspection_engine.py  ← Central orchestrator
        │     ├── sampling_engine.py   (Joel – 2463029)
        │     ├── switching_engine.py  (Joselet – 2463030)
        │     ├── lifecycle_engine.py  (Joseph – 2463031)
        │     ├── rework_engine.py     (Joseph – 2463031)
        │     ├── hold_engine.py       (Joseph – 2463031)
        │     └── recall_engine.py     (Joseph – 2463031)
        ├── product_service.py    (Joel – 2463029)
        ├── supplier_service.py   (Joselet – 2463030)
        └── validation.py         (Shared)
  └── report_generator.py   (Shared)
  └── models.py              (Shared)
```

---

## Module Responsibilities

### `models.py`
Defines all data structures using Python `dataclass`:
- `SamplingPlanEntry`, `DefectClassConfig`, `InspectionResult` (Joel)
- `Supplier`, `ProductionLine`, `SwitchingRecord` (Joselet)
- `Batch`, `RecallRecord`, `CorrectiveAction`, `CustomerComplaint` (Joseph)
- `BatchDecision`, `DecisionCode`, `BatchState`, `InspectionSeverity` (shared)
- `LEGAL_TRANSITIONS` dict enforcing the lifecycle state machine

### `sampling_engine.py` ← Joel Thomas Mario J (2463029)
- `get_code_letter(lot_size)` – lot-size band → code letter
- `SamplingPlanLoader` – CSV loader + indexed lookup
- `SamplingEngine.evaluate()` – per-class defect evaluation
- `SamplingEngine.evaluate_reduced_between()` – REDUCED between-Ac-Re check
- `SamplingEngine.required_sample_size()` – n calculation with BR-03

### `switching_engine.py` ← Joselet K Jaison (2463030)
- `SwitchingEngine.process_decision()` – master switch dispatcher
- `_process_normal()`, `_process_tightened()`, `_process_reduced()` – per-state logic
- `check_discontinued()` – gate-check before any inspection
- `apply_corrective_action()` – BR-06 corrective action handler

### `lifecycle_engine.py` ← Joseph Mangaly (2463031)
- `begin_inspection()` – QUARANTINE → UNDER_INSPECTION
- `mark_late()` – BR-11 48-hour window check
- `try_release()` – shelf-life check (BR-10) + RELEASED transition
- `reject_batch()` – REJECTED transition

### `rework_engine.py` ← Joseph Mangaly (2463031)
- `is_eligible()` – BR-07 eligibility check
- `begin_rework()` – REJECTED → REWORK
- `begin_reinspection()` – REWORK → UNDER_INSPECTION

### `hold_engine.py` ← Joseph Mangaly (2463031)
- `can_place_on_hold()` – 30-day window check
- `place_on_hold()` – RELEASED → ON_HOLD
- `required_hold_sample_size()` – double sample
- `find_related_released_batches()` – cascade finder

### `recall_engine.py` ← Joseph Mangaly (2463031)
- `cascade_recall()` – recall all non-expired same-lot batches
- `check_on_hold_critical()` – BR-09 trigger detection

### `inspection_engine.py` ← Shared
Orchestrates a complete inspection cycle by calling all engines in order:
1. `begin_inspection()` → lifecycle_engine + switching_engine
2. `record_result()` → sampling_engine + lifecycle_engine + switching_engine
3. `apply_decision()` → lifecycle_engine
4. `begin_rework()` → rework_engine
5. `place_on_hold()` → hold_engine
6. `trigger_recall()` → recall_engine
7. `register_corrective_action()` → switching_engine

### `command_parser.py` ← Shared
Reads command CSV files row by row. Dispatches each row to the appropriate handler method. Handles all 12 commands. Returns `CommandResult` list.

### `validation.py` ← Shared
Utility functions: `require_non_empty`, `require_positive_int`, `require_datetime`, `require_choice`, `require_id`, `validate_command_fields`.

### `report_generator.py` ← Shared
Generates all five output CSV reports. Each `write_*` method is independently callable.

### `product_service.py` ← Joel Thomas Mario J (2463029)
In-memory registry for products. CRUD with duplicate-ID detection.

### `supplier_service.py` ← Joselet K Jaison (2463030)
In-memory registry for suppliers and production lines. `get_source()` abstracts over both.

---

## Data Flow

```
Command CSV
    ↓
CommandParser.process_file()
    ↓
Per-command handler (e.g. _cmd_record_result)
    ↓
InspectionEngine.record_result()
    ├── SamplingEngine.evaluate() → SamplingDecision
    ├── LifecycleEngine.mark_late() → is_late flag
    ├── SwitchingEngine.process_decision() → SwitchingRecord(s)
    └── BatchDecision (output)
    ↓
InspectionEngine.apply_decision()
    └── LifecycleEngine.try_release() or .reject_batch()
    ↓
ReportGenerator.generate_all()
    └── 5 CSV output files
```

---

## Design Principles Applied

1. **Single Responsibility** – Each engine handles exactly one aspect of the AQL workflow.
2. **Open/Closed** – New defect classes or severity levels can be added via CSV/config without modifying core algorithms.
3. **Separation of Concerns** – Sampling calculations, switching decisions, and lifecycle transitions are strictly separated.
4. **No External Dependencies** – Only Python standard library (`csv`, `dataclasses`, `enum`, `datetime`, `argparse`).
5. **Deterministic Output** – Same command file + same sampling plan always produces the same outputs.
6. **Fail-Fast Validation** – All inputs are validated before any state change occurs.

