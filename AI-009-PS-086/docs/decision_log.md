# Decision Log

**Project:** AI-009 | PS-086 | Section 6BTAI

This document records all significant design decisions made during the development of the AQL Engine.

---

## DL-001: Sliding Window for BR-04

**Decision:** The "five consecutive batches" window for NORMAL→TIGHTENED switching is implemented as a fixed-size list (`recent_decisions`) of the last 5 boolean values (True=accept, False=reject), maintained on each `Supplier` / `ProductionLine` entity.

**Rationale:** This is the simplest approach that correctly handles the 5-batch boundary. When fewer than 5 batches have been inspected, the window is smaller (a supplier cannot be switched to TIGHTENED based on no history).

**Alternative considered:** Querying the full batch history for the last 5 decisions at evaluation time — rejected due to complexity and potential performance issues with large batch stores.

---

## DL-002: 48-Hour LATE Boundary (BR-11)

**Decision:** `is_late = (recorded_at - sampled_at) > timedelta(hours=48)`. Exactly 48 hours is NOT late.

**Rationale:** The spec says "within 48 hours" — this means ≤ 48h is on time. Edge case EC-10 confirms this.

---

## DL-003: 30-Day Hold Window (BR-08)

**Decision:** `can_hold = days_since_release <= 30`. Exactly 30 days is allowed; 31 days is not.

**Rationale:** "Within 30 days" means the window includes day 30. EC-7 and EC-8 confirm this boundary.

---

## DL-004: 75% Shelf-Life Threshold (BR-10)

**Decision:** `ratio = remaining / total`. Release is allowed if `ratio >= 0.75`. Exactly 75% is allowed.

**Rationale:** "Less than 75%" triggers rejection, so exactly 75% does not. This matches standard pharmaceutical/food safety interpretations of minimum shelf-life requirements.

---

## DL-005: Critical Auto-Reject Mechanism (BR-02)

**Decision:** Critical defects ≥ 1 trigger `REJECTED_CRITICAL` regardless of the CRITICAL AQL's Ac/Re values from the sampling plan.

**Rationale:** BR-02 states "Critical defects of one or more always cause rejection." The AQL sampling plan entries for CRITICAL (AQL=0.065) define the sample size for critical inspection but the rejection threshold is overridden.

---

## DL-006: Rework Reinspection Severity (BR-07)

**Decision:** Rework reinspection always uses TIGHTENED severity, regardless of the supplier's current severity at time of reinspection.

**Rationale:** BR-07 states "Reinspect at TIGHTENED using a new sample." This is an explicit rule, so we do not inherit the supplier's current severity.

**Implementation:** `rework_round > 0` causes `InspectionEngine.record_result()` to override `severity = TIGHTENED`.

---

## DL-007: Command CSV Column Layout

**Decision:** Commands share a single wide CSV header. Each command only populates the columns it needs; unused cells remain empty.

**Rationale:** This avoids per-command CSV files while keeping a simple, human-editable format. The parser reads by column name (via `csv.DictReader`), so column position is irrelevant as long as the header is present.

**Trade-off:** Some rows have many empty cells. This is acceptable for a command-driven batch process where human readability of individual rows is not the primary concern.

---

## DL-008: No External Dependencies

**Decision:** The entire project uses only the Python 3.10 standard library. No `pandas`, `numpy`, `SQLAlchemy`, or other third-party packages.

**Rationale:** Requirement 11.3: "Avoid unnecessary frameworks." The project's data volumes are small enough that in-memory dicts and lists suffice. This also means zero installation friction on any Python 3.10+ environment.

---

## DL-009: DISCONTINUED Flag on Source Entity

**Decision:** `corrective_action_registered: bool` is a field on `Supplier`/`ProductionLine`. It is set to `True` by `SwitchingEngine.apply_corrective_action()`.

**Rationale:** The flag prevents repeated `apply_corrective_action()` calls from incorrectly processing already-active sources. After the action is registered, severity moves to TIGHTENED; subsequent inspections are permitted without re-checking the flag.

---

## DL-010: Recall Cascade Excludes Already-RECALLED Batches

**Decision:** In `cascade_recall()`, batches already in `RECALLED` state are silently skipped (no double-transition attempt).

**Rationale:** `RECALLED` is a terminal state. Attempting a transition from RECALLED to RECALLED would raise `ValueError`. Skipping already-recalled batches is the correct behaviour and avoids false exceptions.


---

## DL-011: Cascade Recall Silently Skips Unreleased States

**Decision:** During cascade recall (BR-09), batches in `QUARANTINE`, `UNDER_INSPECTION`, `REJECTED`, and `REWORK` states that share the same raw-material lot are silently skipped. Only `RELEASED` and `ON_HOLD` batches (which can legally transition to `RECALLED`) are included in the cascade.

**Rationale:** Batches that have not reached the `RELEASED` state have not been distributed to consumers and therefore do not require a consumer-facing recall. `REJECTED` batches are already quarantined from the supply chain. Forcing illegal transitions would raise `ValueError` and abort the recall; catching and skipping is correct business behaviour.

**Implementation:** `recall_engine.py::cascade_recall()` catches `ValueError` from `batch.transition_to(RECALLED)` and skips the batch. The `recalled_batch_ids` list only includes batches that successfully transitioned.

---

## DL-012: ON_HOLD -> UNDER_INSPECTION Added to Legal Transitions

**Decision:** Added `ON_HOLD -> UNDER_INSPECTION` to `LEGAL_TRANSITIONS` in `models.py`.

**Rationale:** BR-08 requires ON_HOLD batches to be reinspected. The base Section 6 lifecycle diagram does not list this transition but BR-08 makes it implicit. Without this transition, reinspection is architecturally impossible — `batch.transition_to(UNDER_INSPECTION)` from ON_HOLD would always raise `ValueError`.

**Implementation:** `begin_hold_inspection()` added to `LifecycleEngine` and `InspectionEngine`. Sets `batch.hold_reinspection = True` to signal double-sample requirement to `InspectionEngine.record_result()`. The flag is reset to `False` by `record_result()` after capturing it.

**Existing test impact:** The existing `test_lifecycle.py` suite tests 10 specific illegal transitions. None of them test `ON_HOLD -> UNDER_INSPECTION` as illegal, so all 29 lifecycle tests continue to pass unmodified.

---

## DL-013: hold_reinspection Flag Captured Before record_result() Reset

**Decision:** In `command_parser._cmd_record_result()`, the value of `batch.hold_reinspection` is captured into a local variable `was_hold_reinspection` **before** calling `engine.record_result()`.

**Rationale:** `record_result()` resets `batch.hold_reinspection = False` internally (after reading and applying the double-sample logic). If the recall-trigger check in `command_parser` read `batch.hold_reinspection` after `record_result()`, the flag would always be `False` and the check would never trigger. By capturing it first, the caller can decide whether to initiate a recall cascade based on the original pre-call state.

**Implementation:**
```python
was_hold_reinspection = batch.hold_reinspection   # capture BEFORE record_result resets it
decision, sw_records = engine.record_result(...)
if was_hold_reinspection and decision.defects.get(DefectClass.CRITICAL, 0) > 0:
    recall = engine.trigger_recall(...)
```
