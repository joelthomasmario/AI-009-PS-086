# Business Rules Reference

**Project:** AI-009 | PS-086 | Section 6BTAI

---

## BR-01: Sampling Plans

**Owner:** Joel Thomas Mario J (2463029)

Lot-size to code-letter mapping:

| Lot Size Range | Code Letter |
|----------------|-------------|
| 2–8 | A |
| 9–15 | B |
| 16–25 | C |
| 26–50 | D |
| 51–90 | E |
| 91–150 | F |
| 151–280 | G |
| 281–500 | H |
| 501–1200 | J |
| 1201–3200 | K |
| 3201–10000 | L |

The sampling plan CSV (`data/sampling_plan.csv`) provides `sample_size (n)`, `Ac` and `Re` for each `(code_letter, AQL, severity)` combination.

**Rule:** Missing entries must never be invented. A `KeyError` is raised if the combination is absent.

---

## BR-02: Defect Classification

**Owner:** Joel Thomas Mario J (2463029)

| Class | Default AQL |
|-------|------------|
| CRITICAL | 0.065 |
| MAJOR | 1.0 |
| MINOR | 2.5 |

- Each class is evaluated independently.
- A batch is rejected if **any class** reaches or exceeds its `Re`.
- **Critical defects ≥ 1 always cause rejection**, regardless of `Ac`/`Re`.

---

## BR-03: Sample Size

**Owner:** Joel Thomas Mario J (2463029)

If the sampling plan's `sample_size ≥ lot_size`, inspect 100% of the lot (set `effective_sample_size = lot_size`). The `full_lot_inspection` flag is set to `True` and `BR-03` is added to `rule_ids`.

---

## BR-04: Switching – NORMAL ↔ TIGHTENED, TIGHTENED → DISCONTINUED, NORMAL → REDUCED

**Owner:** Joselet K Jaison (2463030)

| Transition | Trigger |
|-----------|---------|
| NORMAL → TIGHTENED | ≥ 2 rejections in the last 5 consecutive batches |
| TIGHTENED → NORMAL | 5 consecutive acceptances while TIGHTENED |
| TIGHTENED → DISCONTINUED | 5 cumulative rejections while TIGHTENED |
| NORMAL → REDUCED | 10 consecutive acceptances AND total defects ≤ Ac(REDUCED) |

**Note:** Only non-LATE results count toward the NORMAL→REDUCED consecutive-accept counter (see BR-11).

---

## BR-05: REDUCED Switching

**Owner:** Joselet K Jaison (2463030)

Switch from REDUCED to NORMAL when **any** of these occurs:

1. A rejection occurs.
2. A result falls **between Ac and Re** (i.e., `Ac < defects < Re`). The batch is **accepted**, but severity switches back to NORMAL.
3. A production irregularity occurs: gap between consecutive inspection timestamps exceeds **30 days**.

---

## BR-06: DISCONTINUED

**Owner:** Joselet K Jaison (2463030)

- No inspections are permitted on a DISCONTINUED source until a corrective action record is registered.
- After corrective action registration: severity resumes at **TIGHTENED**.
- Attempting to inspect a DISCONTINUED source without corrective action raises `PermissionError`.

---

## BR-07: Rework

**Owner:** Joseph Mangaly (2463031)

A rejected batch may be reworked **once** if:
- Critical defects at the time of rejection = 0.
- Major defects ≤ 2 × Re(MAJOR).

Rework lifecycle: `REJECTED → REWORK → UNDER_INSPECTION` (at TIGHTENED severity).

A second rejection after rework is **final** (no further rework allowed; `rework_count` is checked).

---

## BR-08: Hold

**Owner:** Joseph Mangaly (2463031)

A RELEASED batch may be placed ON_HOLD if:
- A related batch (same supplier + same `raw_material_lot_id`) is subsequently rejected due to a critical defect.
- The hold request is made within **30 days** of the batch's release date (exactly 30 days is allowed; 31 days is not).

ON_HOLD reinspection uses **double** the standard sample size.

---

## BR-09: Recall

**Owner:** Joseph Mangaly (2463031)

**Trigger conditions:**
1. A critical defect is found during ON_HOLD reinspection.
2. A `COMPLAINT` command cites the batch.
3. A `RECALL` command is issued directly.

**Cascade:** All batches sharing the same `raw_material_lot_id` that:
- Have not **expired** (`expiry_date > recall_timestamp`).
- Are not already in `RECALLED` state.

...are transitioned to `RECALLED` (terminal state).

---

## BR-10: Shelf Life and Release

**Owner:** Joseph Mangaly (2463031)

A batch **cannot be released** if:

```
remaining_shelf_life_days / total_shelf_life_days < 0.75
```

Such batches are moved to `REJECTED` with `rejection_reason = "SHORT_DATED"`. The `is_short_dated` flag is set to `True`.

**Note:** Exactly 75% remaining is allowed (threshold is strictly less than 75%).

---

## BR-11: Decision Timing

**Shared**

Inspection results must be recorded within **48 hours** of sampling.

- Results recorded > 48 hours after `sampled_at` are accepted but marked `is_late = True`.
- Exactly 48 hours is **not** considered late.
- **LATE results must not count toward NORMAL → REDUCED switching** (the consecutive-accept counter is not incremented for late results).
- `BR-11` is appended to `rule_ids` for late results.

