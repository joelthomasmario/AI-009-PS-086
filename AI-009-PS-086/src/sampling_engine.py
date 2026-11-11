"""
sampling_engine.py – AQL lot-size code-letter lookup, sample-size calculation
and per-defect-class accept/reject evaluation.

Module Owner: Joel Thomas Mario J (2463029)
Team: AI-009  Section: 6BTAI

Business Rules implemented here:
  BR-01 – Sampling plan lookup (code letter, Ac, Re)
  BR-02 – Defect classification and per-class evaluation
  BR-03 – 100% inspection when sample_size >= lot_size
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .models import (
    BatchDecision,
    DecisionCode,
    DefectClass,
    DefectClassConfig,
    InspectionResult,
    InspectionSeverity,
    SamplingPlanEntry,
)

# ---------------------------------------------------------------------------
# Lot-size to code-letter mapping (BR-01)
# ---------------------------------------------------------------------------

# Each entry: (lower_inclusive, upper_inclusive, code_letter)
_LOT_SIZE_BANDS: List[Tuple[int, int, str]] = [
    (2,     8,     "A"),
    (9,     15,    "B"),
    (16,    25,    "C"),
    (26,    50,    "D"),
    (51,    90,    "E"),
    (91,    150,   "F"),
    (151,   280,   "G"),
    (281,   500,   "H"),
    (501,   1200,  "J"),
    (1201,  3200,  "K"),
    (3201,  10000, "L"),
]


def get_code_letter(lot_size: int) -> str:
    """Return the AQL code letter for a given lot size (BR-01).

    Args:
        lot_size: Total number of units in the lot.

    Returns:
        Single uppercase letter ('A' through 'L').

    Raises:
        ValueError: If lot_size < 2 or > 10 000 (outside defined bands).
    """
    if lot_size < 2:
        raise ValueError(f"Lot size {lot_size} is below the minimum of 2.")
    for lo, hi, letter in _LOT_SIZE_BANDS:
        if lo <= lot_size <= hi:
            return letter
    raise ValueError(
        f"Lot size {lot_size} exceeds the maximum defined band (10 000). "
        "Extend the sampling plan bands as required."
    )


# ---------------------------------------------------------------------------
# Sampling plan loader (BR-01)
# ---------------------------------------------------------------------------

class SamplingPlanLoader:
    """Loads the AQL sampling plan from a CSV file and indexes it.

    Joel Thomas Mario J – 2463029

    Expected CSV columns (case-insensitive, whitespace-stripped):
        code_letter, aql, severity, sample_size, ac, re

    Usage::

        loader = SamplingPlanLoader("data/sampling_plan.csv")
        entry = loader.lookup("G", 1.0, InspectionSeverity.NORMAL)
    """

    def __init__(self, csv_path: str) -> None:
        self._csv_path = csv_path
        # Key: (code_letter, aql, severity) -> SamplingPlanEntry
        self._index: Dict[Tuple[str, float, InspectionSeverity], SamplingPlanEntry] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._csv_path):
            raise FileNotFoundError(
                f"Sampling plan CSV not found: {self._csv_path}\n"
                "Please supply data/sampling_plan.csv with columns: "
                "code_letter, aql, severity, sample_size, ac, re"
            )

        with open(self._csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise ValueError("Sampling plan CSV is empty or has no header row.")
            # Normalise headers
            norm_headers = [h.strip().lower() for h in reader.fieldnames]
            required = {"code_letter", "aql", "severity", "sample_size", "ac", "re"}
            missing = required - set(norm_headers)
            if missing:
                raise ValueError(
                    f"Sampling plan CSV missing required columns: {missing}. "
                    f"Found: {norm_headers}"
                )

            for row_num, raw_row in enumerate(reader, start=2):
                row = {k.strip().lower(): v.strip() for k, v in raw_row.items()}
                try:
                    letter = row["code_letter"].upper()
                    aql = float(row["aql"])
                    sev = InspectionSeverity(row["severity"].upper())
                    n = int(row["sample_size"])
                    ac = int(row["ac"])
                    re = int(row["re"])
                except (KeyError, ValueError) as exc:
                    raise ValueError(
                        f"Sampling plan CSV row {row_num} is malformed: {exc} | row={row}"
                    ) from exc

                entry = SamplingPlanEntry(
                    code_letter=letter,
                    aql=aql,
                    severity=sev,
                    sample_size=n,
                    ac=ac,
                    re=re,
                )
                key = (letter, aql, sev)
                if key in self._index:
                    raise ValueError(
                        f"Duplicate entry in sampling plan CSV at row {row_num}: "
                        f"code_letter={letter}, aql={aql}, severity={sev.value}"
                    )
                self._index[key] = entry

        if not self._index:
            raise ValueError("Sampling plan CSV contains no data rows.")

    def lookup(
        self,
        code_letter: str,
        aql: float,
        severity: InspectionSeverity,
    ) -> SamplingPlanEntry:
        """Look up a sampling plan entry.

        Args:
            code_letter: AQL code letter.
            aql: AQL value (must match a value in the CSV).
            severity: Inspection severity level.

        Returns:
            The matching SamplingPlanEntry.

        Raises:
            KeyError: If no entry exists for the given combination (BR-01
                      forbids inventing missing values).
        """
        key = (code_letter.upper(), float(aql), severity)
        if key not in self._index:
            raise KeyError(
                f"No sampling plan entry for code_letter={code_letter}, "
                f"aql={aql}, severity={severity.value}. "
                "Per BR-01, missing values must not be invented. "
                "Add the entry to the sampling plan CSV."
            )
        return self._index[key]

    @property
    def entries(self) -> List[SamplingPlanEntry]:
        return list(self._index.values())


# ---------------------------------------------------------------------------
# Sampling engine (BR-01, BR-02, BR-03)
# ---------------------------------------------------------------------------

@dataclass
class PerClassEvaluation:
    """Result of evaluating one defect class against its sampling plan."""
    defect_class: DefectClass
    aql: float
    code_letter: str
    sample_size: int
    ac: int
    re: int
    defect_count: int
    accepted: bool          # True if defect_count < re
    critical_auto_reject: bool = False   # BR-02: any critical defect -> reject


@dataclass
class SamplingDecision:
    """Aggregated decision from evaluating all defect classes for a batch."""
    batch_id: str
    lot_size: str
    code_letter: str
    severity: InspectionSeverity
    effective_sample_size: int        # may equal lot_size if 100% (BR-03)
    full_lot_inspection: bool         # True if BR-03 triggered
    per_class: List[PerClassEvaluation]
    overall_accepted: bool
    primary_rejection_class: Optional[DefectClass]
    decision_code: DecisionCode
    decision_reason: str
    rule_ids: List[str]


class SamplingEngine:
    """Calculates sample sizes and evaluates inspection results for a batch.

    Joel Thomas Mario J – 2463029

    Usage::

        engine = SamplingEngine(plan_loader, product)
        decision = engine.evaluate(batch, inspection_result, severity)
    """

    def __init__(self, plan_loader: SamplingPlanLoader) -> None:
        self._loader = plan_loader

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def required_sample_size(
        self,
        lot_size: int,
        aql: float,
        severity: InspectionSeverity,
    ) -> Tuple[int, str, bool]:
        """Return (sample_size, code_letter, is_100_pct).

        BR-03: If the plan sample size >= lot_size, return lot_size.

        Args:
            lot_size: Total units in the lot.
            aql: AQL to use for the lookup (normally the MAJOR AQL).
            severity: Current inspection severity.

        Returns:
            Tuple of (actual_sample_size, code_letter, full_lot_flag).
        """
        code_letter = get_code_letter(lot_size)
        entry = self._loader.lookup(code_letter, aql, severity)

        if entry.sample_size >= lot_size:
            # BR-03: 100% inspection
            return lot_size, code_letter, True

        return entry.sample_size, code_letter, False

    def evaluate(
        self,
        batch_id: str,
        lot_size: int,
        defect_configs: List[DefectClassConfig],
        result: InspectionResult,
        severity: InspectionSeverity,
    ) -> SamplingDecision:
        """Evaluate an inspection result against all defect classes.

        Args:
            batch_id: Batch under evaluation.
            lot_size: Lot size (for code-letter and BR-03 check).
            defect_configs: Per-class AQL configuration from the product.
            result: Recorded inspection result.
            severity: Current inspection severity (from supplier/line).

        Returns:
            SamplingDecision with overall accept/reject and per-class breakdown.
        """
        code_letter = get_code_letter(lot_size)
        per_class: List[PerClassEvaluation] = []
        rule_ids: List[str] = ["BR-01", "BR-02"]

        # BR-03: check for 100% inspection
        # We use the MAJOR AQL for primary n calculation
        major_aql = self._get_major_aql(defect_configs)
        major_entry = self._loader.lookup(code_letter, major_aql, severity)
        full_lot = major_entry.sample_size >= lot_size
        effective_n = lot_size if full_lot else result.sample_size

        if full_lot:
            rule_ids.append("BR-03")

        # Evaluate each defect class independently (BR-02)
        any_rejected = False
        primary_rejection_class: Optional[DefectClass] = None
        decision_reason_parts: List[str] = []

        for dc_cfg in defect_configs:
            entry = self._loader.lookup(code_letter, dc_cfg.aql, severity)
            count = result.defects_for(dc_cfg.defect_class)

            # BR-02: Critical >= 1 always rejects
            critical_auto = (
                dc_cfg.defect_class == DefectClass.CRITICAL and count >= 1
            )
            # Standard rule: reject if count >= Re
            standard_reject = count >= entry.re

            accepted = not (critical_auto or standard_reject)

            ev = PerClassEvaluation(
                defect_class=dc_cfg.defect_class,
                aql=dc_cfg.aql,
                code_letter=code_letter,
                sample_size=effective_n,
                ac=entry.ac,
                re=entry.re,
                defect_count=count,
                accepted=accepted,
                critical_auto_reject=critical_auto,
            )
            per_class.append(ev)

            if not accepted:
                any_rejected = True
                if primary_rejection_class is None:
                    primary_rejection_class = dc_cfg.defect_class
                if critical_auto:
                    decision_reason_parts.append(
                        f"CRITICAL defect count={count} (>=1 triggers rejection per BR-02)"
                    )
                else:
                    decision_reason_parts.append(
                        f"{dc_cfg.defect_class.value} defects={count} >= Re={entry.re}"
                    )

        if any_rejected:
            if primary_rejection_class == DefectClass.CRITICAL:
                decision_code = DecisionCode.REJECTED_CRITICAL
            else:
                decision_code = DecisionCode.REJECTED
            decision_reason = "; ".join(decision_reason_parts)
        else:
            decision_code = DecisionCode.ACCEPTED
            decision_reason = "All defect classes within acceptance limits"

        return SamplingDecision(
            batch_id=batch_id,
            lot_size=str(lot_size),
            code_letter=code_letter,
            severity=severity,
            effective_sample_size=effective_n,
            full_lot_inspection=full_lot,
            per_class=per_class,
            overall_accepted=not any_rejected,
            primary_rejection_class=primary_rejection_class,
            decision_code=decision_code,
            decision_reason=decision_reason,
            rule_ids=rule_ids,
        )

    def evaluate_reduced_between(
        self,
        batch_id: str,
        lot_size: int,
        defect_configs: List[DefectClassConfig],
        result: InspectionResult,
        severity: InspectionSeverity,
    ) -> Tuple[SamplingDecision, bool]:
        """Evaluate a REDUCED inspection result, also checking between-Ac-and-Re (BR-05).

        Returns:
            (SamplingDecision, between_ac_and_re_flag)
            If between_ac_and_re_flag is True, the batch is ACCEPTED but
            severity must switch back to NORMAL (caller's responsibility).
        """
        decision = self.evaluate(batch_id, lot_size, defect_configs, result, severity)
        between = False

        if severity == InspectionSeverity.REDUCED and decision.overall_accepted:
            code_letter = get_code_letter(lot_size)
            for dc_cfg in defect_configs:
                entry = self._loader.lookup(code_letter, dc_cfg.aql, severity)
                count = result.defects_for(dc_cfg.defect_class)
                # between Ac and Re means count > Ac AND count < Re
                if entry.ac < count < entry.re:
                    between = True
                    break

        return decision, between

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_major_aql(defect_configs: List[DefectClassConfig]) -> float:
        for dc in defect_configs:
            if dc.defect_class == DefectClass.MAJOR:
                return dc.aql
        # Fallback to default
        return 1.0



