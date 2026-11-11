# Design Document

**Project:** AQL Sampling, Inspection Severity and Batch Release Engine  
**Project ID:** AI-009 | **PS:** PS-086 | **Section:** 6BTAI  
**Team:** Joel Thomas Mario J (2463029), Joselet K Jaison (2463030), Joseph Mangaly (2463031)

---

## 1. Problem Definition

Manufacturing companies receive raw material batches from external suppliers and also produce finished goods on internal production lines. Before these batches enter inventory or are shipped to customers, they must be inspected to ensure quality. The challenge is:

- **How many units** to inspect from each lot (sample size calculation).
- **Whether to accept or reject** the lot based on defect counts.
- **How to adjust inspection stringency** based on a supplier's historical performance.
- **What to do after rejection** (rework, hold, recall).

The AQL (Acceptable Quality Level) standard, based on ISO 2859-1, provides a statistically grounded framework for all of these decisions.

---

## 2. Objectives

1. Implement a complete, rules-based AQL inspection engine covering all 11 business rules.
2. Support both supplier-side (incoming) and production-line-side (in-process) inspection.
3. Provide a command-file–driven CLI interface for deterministic, automated operation.
4. Generate five standard output reports for audit and traceability.
5. Enforce batch lifecycle state transitions with full validation.
6. Provide 144 automated tests covering all business rules, edge cases, and error conditions.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                            │
└──────────────────┬──────────────────────────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │  command_parser.py │  Reads CSV, dispatches commands
         └──────┬─────────────┘
                │
    ┌───────────▼────────────────────────────────────┐
    │            inspection_engine.py                │
    │         (Central Orchestrator)                 │
    └───┬──────────┬──────────┬──────────┬───────────┘
        │          │          │          │
  ┌─────▼──┐ ┌────▼────┐ ┌───▼────┐ ┌──▼──────────┐
  │sampling│ │switch   │ │lifecy- │ │rework/hold/ │
  │_engine │ │_engine  │ │cle_eng │ │recall_engine│
  └─────┬──┘ └────┬────┘ └───┬────┘ └──────┬──────┘
        │          │          │             │
  ┌─────▼──────────▼──────────▼─────────────▼──────┐
  │                   models.py                      │
  │  Batch, Supplier, ProductionLine, Product, etc.  │
  └──────────────────────────────────────────────────┘
        │
  ┌─────▼──────────────┐
  │  report_generator  │  → 5 CSV output files
  └────────────────────┘
```

---

## 4. Entity Descriptions and Relationships

### Product
- Owned by: Joel Thomas Mario J
- Attributes: `product_id`, `name`, `defect_configs` (list of AQL per class), `total_shelf_life_days`
- Relationship: One product → many batches

### Supplier / ProductionLine
- Owned by: Joselet K Jaison
- Attributes: `severity` (current), `consecutive_accepts`, `tightened_reject_count`, `recent_decisions` (sliding window), `switching_history`
- Relationship: One source → many batches; each source maintains its own inspection severity

### Batch
- Owned by: Joseph Mangaly
- Attributes: `batch_id`, `product_id`, `source_id`, `lot_size`, `raw_material_lot_id`, `state`, `inspection_results`, `state_history`
- Relationship: One batch → one product, one source, many inspection results

### SamplingPlanEntry
- Owned by: Joel Thomas Mario J
- Loaded from CSV. Key: `(code_letter, aql, severity)` → `(sample_size, Ac, Re)`

### InspectionResult
- Owned by: Joel Thomas Mario J
- Attributes: `batch_id`, `sample_size`, `defects` (by class), `sampled_at`, `recorded_at`, `is_late`, `rework_round`

### SwitchingRecord
- Owned by: Joselet K Jaison
- Attributes: `source_id`, `previous_severity`, `new_severity`, `triggering_batch_id`, `rule_id`, `event`, `timestamp`

### BatchDecision
- Shared output model
- Full audit record of one inspection event (see Section 8 of spec)

### RecallRecord / CorrectiveAction / CustomerComplaint
- Owned by: Joseph Mangaly

---

## 5. Module Ownership

| Module | Owner | Roll No |
|--------|-------|---------|
| `sampling_engine.py` | Joel Thomas Mario J | 2463029 |
| `product_service.py` | Joel Thomas Mario J | 2463029 |
| `switching_engine.py` | Joselet K Jaison | 2463030 |
| `supplier_service.py` | Joselet K Jaison | 2463030 |
| `lifecycle_engine.py` | Joseph Mangaly | 2463031 |
| `rework_engine.py` | Joseph Mangaly | 2463031 |
| `hold_engine.py` | Joseph Mangaly | 2463031 |
| `recall_engine.py` | Joseph Mangaly | 2463031 |
| `models.py` | Shared | All |
| `inspection_engine.py` | Shared | All |
| `command_parser.py` | Shared | All |
| `validation.py` | Shared | All |
| `report_generator.py` | Shared | All |
| `main.py` | Shared | All |

---

## 6. Business Rules

See `docs/business_rules.md` for full rule text and pseudocode.

---

## 7. Algorithms and Pseudocode

### Lot-Size to Code Letter (BR-01)
```
function get_code_letter(lot_size):
    for each (lo, hi, letter) in LOT_SIZE_BANDS:
        if lo <= lot_size <= hi:
            return letter
    raise ValueError
```

### Sampling Plan Evaluation (BR-01, BR-02, BR-03)
```
function evaluate(batch, lot_size, defect_configs, result, severity):
    code_letter = get_code_letter(lot_size)
    for each defect_class_config in defect_configs:
        entry = plan_loader.lookup(code_letter, config.aql, severity)
        count = result.defects[config.defect_class]
        if config.defect_class == CRITICAL and count >= 1:
            → REJECTED_CRITICAL
        if count >= entry.re:
            → REJECTED
    if no rejections:
        → ACCEPTED
```

### Switching Logic (BR-04)
```
# NORMAL → TIGHTENED
if recent_decisions[-5:].count(False) >= 2:
    switch to TIGHTENED

# TIGHTENED → NORMAL
if consecutive_accepts >= 5:
    switch to NORMAL

# TIGHTENED → DISCONTINUED
if tightened_reject_count >= 5:
    switch to DISCONTINUED

# NORMAL → REDUCED
if consecutive_accepts >= 10 and total_defects <= reduced_ac:
    switch to REDUCED
```

### Shelf Life Check (BR-10)
```
ratio = remaining_days / total_shelf_life_days
if ratio < 0.75:
    batch.state = REJECTED
    batch.rejection_reason = "SHORT_DATED"
```

### Recall Cascade (BR-09)
```
function cascade_recall(all_batches, raw_material_lot_id, timestamp):
    for each batch in all_batches:
        if batch.raw_material_lot_id != raw_material_lot_id: skip
        if batch.expiry_date <= timestamp: skip  # expired
        if batch.state == RECALLED: skip  # already terminal
        batch.transition_to(RECALLED)
```

---

## 8. Lifecycle Transition Diagram

```
                  ┌─────────────┐
                  │  QUARANTINE  │
                  └──────┬───────┘
                         │ BEGIN_INSPECTION
                         ▼
                  ┌──────────────────┐
                  │  UNDER_INSPECTION │◄─────────────┐
                  └──┬───┬───────┬───┘               │
        ACCEPTED      │   │REJECT │                   │
            ──────────┘   │       │ON_HOLD            │
            │             │       │                   │
            ▼             ▼       ▼         REWORK    │
       ┌──────────┐  ┌────────┐  ┌────────┐  ┌──────┤
       │ RELEASED │  │REJECTED│  │ON_HOLD │  │REWORK│
       └──┬───┬───┘  └───┬────┘  └──┬─┬──┘  └──────┘
  ON_HOLD │   │RECALL    │REWORK    │ │          ▲
          │   │          └──────────┘ │          │
          ▼   │                       │          │
       ┌──────┤◄──────────────────────┘          │
       │ON_HOLD│  (also from RELEASED)            │
       └──┬─┬──┘                                 │
    CLEAR │ │ RECALL                             │
          ▼ │                                    │
     RELEASED│ (from ON_HOLD)                   │
             │                                   │
             ▼                                   │
         ┌────────┐                              │
         │RECALLED│ (terminal)                   │
         └────────┘                              │
                                                 │
   REJECTED ──── REWORK ──────────────────────► UNDER_INSPECTION
```

---

## 9. Switching State Diagram

```
     ┌────────────────────────────────────────────────────┐
     │                      NORMAL                         │
     │  entry: consecutive_accepts=0                       │
     └──────┬───────────────────────────────┬─────────────┘
            │ 2 rejects in last 5 (BR-04)   │ 10 consec. accepts +
            │                               │ defects ≤ REDUCED Ac (BR-04)
            ▼                               ▼
     ┌──────────────┐               ┌──────────────┐
     │  TIGHTENED   │               │   REDUCED    │
     │              │               │              │
     └──┬────────┬──┘               └──┬───────────┘
        │        │                     │ any rejection, between-Ac-Re,
        │5 consec│5 cumul.             │ or gap > 30 days (BR-05)
        │accepts │rejects              │
        │(BR-04) │(BR-04)             ▼
        ▼        ▼               → NORMAL (BR-05)
      NORMAL  DISCONTINUED
                │
                │ corrective action registered (BR-06)
                ▼
            TIGHTENED
```

---

## 10. Error Handling

| Error Condition | Handler | Response |
|----------------|---------|----------|
| Missing CSV file | `FileNotFoundError` | Descriptive message with file path |
| Malformed CSV row | `ValueError` | Row number and field name in message |
| Duplicate entity ID | `ValueError` | "already registered" message |
| Unknown command | `CommandResult.success=False` | Lists valid commands |
| Illegal state transition | `ValueError` | Shows current and target state |
| DISCONTINUED without corrective action | `PermissionError` | Cites BR-06 |
| Missing sampling plan entry | `KeyError` | Cites BR-01; no value invention |
| Lot size out of bands | `ValueError` | Shows valid range |
| Rework on ineligible batch | Returns `(False, reason)` | No exception; caller handles |
| Hold window expired | Returns `(False, reason)` | No exception; caller handles |

---

## 11. Edge-Case Handling

| Edge Case | Rule | Implementation |
|-----------|------|----------------|
| Lot = 280 → code G | BR-01 | Band: 151–280 = G |
| Lot = 281 → code H | BR-01 | Band: 281–500 = H |
| Defects = Ac | BR-02 | `accepted = count < re`; Ac is accepted |
| Defects = Re | BR-02 | `accepted = count < re`; Re triggers rejection |
| Exactly 48h recording | BR-11 | `gap > 48h` (strict greater-than) |
| Hold exactly 30 days | BR-08 | `days_since_release > 30` (strict greater-than) |
| Expired batch in recall | BR-09 | `expiry_date <= timestamp` → excluded |
| 2×Re major defects | BR-07 | `major_count <= 2 * major_re` → eligible |
| 5th-previous rejection | BR-04 | Sliding window of exactly 5 decisions |


---

## 12. ON_HOLD Reinspection (BR-08 Extension)

### Background

BR-08 states that a released batch placed ON_HOLD must be reinspected using double the standard sample size. The base lifecycle diagram (Section 6) does not explicitly show an `ON_HOLD -> UNDER_INSPECTION` transition, but BR-08 makes it implicit. This section documents the design decision and implementation.

### Lifecycle Transition Added

`ON_HOLD -> UNDER_INSPECTION` was added to `LEGAL_TRANSITIONS` in `models.py`:

```python
BatchState.ON_HOLD: [BatchState.UNDER_INSPECTION, BatchState.RELEASED,
                     BatchState.REJECTED, BatchState.RECALLED],
```

This supplements the base Section 6 diagram. Without this transition, ON_HOLD reinspection is architecturally impossible.

### New Fields and Methods

| Item | Location | Purpose |
|------|----------|---------|
| `Batch.hold_reinspection: bool` | `models.py` | Flag set True when ON_HOLD batch enters UNDER_INSPECTION for reinspection. Signals double sample size to `InspectionEngine.record_result()`. Reset to False after result is recorded. |
| `LifecycleEngine.begin_hold_inspection()` | `lifecycle_engine.py` | Transitions ON_HOLD -> UNDER_INSPECTION and sets `hold_reinspection = True`. |
| `InspectionEngine.begin_hold_inspection()` | `inspection_engine.py` | Checks DISCONTINUED status (BR-06), then delegates to `LifecycleEngine`. |

### Reinspection Flow

```
1. HOLD command          RELEASED -> ON_HOLD  (must be within 30 days of release)
2. BEGIN_INSPECTION      ON_HOLD  -> UNDER_INSPECTION
   (on ON_HOLD batch)              batch.hold_reinspection = True
3. RECORD_RESULT         sample_size = min(2 * standard_n, lot_size)
                         rule_ids includes "BR-08"
                         batch.hold_reinspection = False  (reset)
4a. Critical defect ->   UNDER_INSPECTION -> REJECTED  (apply_decision)
                         trigger_recall() -> cascade to same raw-material lot (BR-09)
4b. Pass ->              UNDER_INSPECTION -> RELEASED  (apply_decision + try_release + BR-10)
4c. Fail (non-critical)->UNDER_INSPECTION -> REJECTED  (apply_decision)
```

### Algorithm: Double Sample Size (BR-08)

```
standard_n, code_letter, is_100pct = sampler.required_sample_size(lot_size, major_aql, severity)
if batch.hold_reinspection:
    doubled = standard_n * 2
    result.sample_size = min(doubled, lot_size)
    # If doubled >= lot_size, 100% inspection is effectively performed
    batch.hold_reinspection = False
else:
    result.sample_size = lot_size if is_100pct else standard_n
```

### Cascade Recall Exclusions (DL-011)

During cascade recall (BR-09), batches in `QUARANTINE`, `UNDER_INSPECTION`, `REJECTED`, and `REWORK` states that share the same raw-material lot are silently skipped. Only batches that can legally transition to `RECALLED` (i.e., `RELEASED` and `ON_HOLD`) are included.

**Rationale:** Batches that have not reached the RELEASED state have not been distributed to consumers and therefore do not require a consumer-facing recall. REJECTED batches are already quarantined from the supply chain.

**Implementation:** `recall_engine.py::cascade_recall()` catches `ValueError` from `batch.transition_to(RECALLED)` and skips the batch.

### Module Ownership

This feature is owned by **Joseph Mangaly (2463031)** in line with the lifecycle/hold/recall module ownership declared in Section 9.

### Command Parser Integration

`_cmd_begin_inspection()` in `command_parser.py` detects the batch state before dispatching:

```python
if batch.state == BatchState.ON_HOLD:
    self._engine.begin_hold_inspection(batch, source, ts)
else:
    self._engine.begin_inspection(batch, source, ts)
```

`_cmd_record_result()` captures `was_hold_reinspection = batch.hold_reinspection` **before** calling `record_result()` (which resets the flag internally), then checks the pre-captured value to decide whether to trigger recall:

```python
was_hold_reinspection = batch.hold_reinspection
decision, sw_records = engine.record_result(...)
if was_hold_reinspection and decision.defects.get(DefectClass.CRITICAL, 0) > 0:
    recall = engine.trigger_recall(...)
```
