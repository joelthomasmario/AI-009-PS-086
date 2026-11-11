"""
report_generator.py – Generates all required CSV output reports.

Shared module – AI-009
Team: AI-009  Section: 6BTAI

Outputs:
  1. batch_decisions.csv
  2. switching_history.csv
  3. release_register.csv
  4. recall_register.csv
  5. decision_log.csv
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any, Dict, List

from .models import (
    Batch,
    BatchDecision,
    BatchState,
    DefectClass,
    RecallRecord,
    SwitchingRecord,
)


def _fmt(value: Any) -> str:
    """Format a value for CSV output."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(value, (list, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return "|".join(f"{k.value if hasattr(k,'value') else k}={v}" for k, v in value.items())
    if hasattr(value, "value"):  # Enum
        return str(value.value)
    return str(value)


class ReportGenerator:
    """Generates the five standard output CSV reports.

    Shared module – AI-009

    Args:
        output_dir: Directory where report CSV files will be written.
    """

    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. batch_decisions.csv
    # ------------------------------------------------------------------

    def write_batch_decisions(self, decisions: List[BatchDecision]) -> str:
        """Write batch_decisions.csv.

        Each row contains the full decision record per BR-08 reporting spec.

        Returns:
            Absolute path to the written file.
        """
        path = os.path.join(self._output_dir, "batch_decisions.csv")
        fieldnames = [
            "decision_id", "batch_id", "product_id", "source_id",
            "lot_size", "code_letter", "severity",
            "sample_size",
            "defects_critical", "defects_major", "defects_minor",
            "ac_critical", "ac_major", "ac_minor",
            "re_critical", "re_major", "re_minor",
            "decision", "decision_reason", "rule_ids",
            "sampled_at", "recorded_at", "is_late",
        ]

        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for d in decisions:
                writer.writerow({
                    "decision_id":      _fmt(d.decision_id),
                    "batch_id":         _fmt(d.batch_id),
                    "product_id":       _fmt(d.product_id),
                    "source_id":        _fmt(d.source_id),
                    "lot_size":         _fmt(d.lot_size),
                    "code_letter":      _fmt(d.code_letter),
                    "severity":         _fmt(d.severity),
                    "sample_size":      _fmt(d.sample_size),
                    "defects_critical": _fmt(d.defects.get(DefectClass.CRITICAL, 0)),
                    "defects_major":    _fmt(d.defects.get(DefectClass.MAJOR, 0)),
                    "defects_minor":    _fmt(d.defects.get(DefectClass.MINOR, 0)),
                    "ac_critical":      _fmt(d.ac_values.get(DefectClass.CRITICAL, "")),
                    "ac_major":         _fmt(d.ac_values.get(DefectClass.MAJOR, "")),
                    "ac_minor":         _fmt(d.ac_values.get(DefectClass.MINOR, "")),
                    "re_critical":      _fmt(d.re_values.get(DefectClass.CRITICAL, "")),
                    "re_major":         _fmt(d.re_values.get(DefectClass.MAJOR, "")),
                    "re_minor":         _fmt(d.re_values.get(DefectClass.MINOR, "")),
                    "decision":         _fmt(d.decision),
                    "decision_reason":  _fmt(d.decision_reason),
                    "rule_ids":         "|".join(d.rule_ids),
                    "sampled_at":       _fmt(d.sampled_at),
                    "recorded_at":      _fmt(d.recorded_at),
                    "is_late":          _fmt(d.is_late),
                })
        return path

    # ------------------------------------------------------------------
    # 2. switching_history.csv
    # ------------------------------------------------------------------

    def write_switching_history(self, records: List[SwitchingRecord]) -> str:
        """Write switching_history.csv.

        Returns:
            Absolute path to the written file.
        """
        path = os.path.join(self._output_dir, "switching_history.csv")
        fieldnames = [
            "record_id", "source_id",
            "previous_severity", "new_severity",
            "triggering_batch_id", "rule_id", "event", "timestamp",
        ]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow({
                    "record_id":           _fmt(r.record_id),
                    "source_id":           _fmt(r.source_id),
                    "previous_severity":   _fmt(r.previous_severity),
                    "new_severity":        _fmt(r.new_severity),
                    "triggering_batch_id": _fmt(r.triggering_batch_id),
                    "rule_id":             _fmt(r.rule_id),
                    "event":               _fmt(r.event),
                    "timestamp":           _fmt(r.timestamp),
                })
        return path

    # ------------------------------------------------------------------
    # 3. release_register.csv
    # ------------------------------------------------------------------

    def write_release_register(self, batches: List[Batch]) -> str:
        """Write release_register.csv (all batches that reached RELEASED).

        Returns:
            Absolute path to the written file.
        """
        path = os.path.join(self._output_dir, "release_register.csv")
        released = [
            b for b in batches
            if any(state == BatchState.RELEASED for state, _, _ in b.state_history)
        ]

        fieldnames = [
            "batch_id", "product_id", "source_id", "lot_size",
            "raw_material_lot_id", "manufacture_date", "expiry_date",
            "released_at", "current_state",
        ]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for b in released:
                writer.writerow({
                    "batch_id":            _fmt(b.batch_id),
                    "product_id":          _fmt(b.product_id),
                    "source_id":           _fmt(b.source_id),
                    "lot_size":            _fmt(b.lot_size),
                    "raw_material_lot_id": _fmt(b.raw_material_lot_id),
                    "manufacture_date":    _fmt(b.manufacture_date),
                    "expiry_date":         _fmt(b.expiry_date),
                    "released_at":         _fmt(b.released_at),
                    "current_state":       _fmt(b.state),
                })
        return path

    # ------------------------------------------------------------------
    # 4. recall_register.csv
    # ------------------------------------------------------------------

    def write_recall_register(self, recalls: List[RecallRecord]) -> str:
        """Write recall_register.csv.

        Returns:
            Absolute path to the written file.
        """
        path = os.path.join(self._output_dir, "recall_register.csv")
        fieldnames = [
            "recall_id", "trigger_batch_id",
            "recalled_batch_ids", "reason", "rule_id", "recalled_at",
        ]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in recalls:
                writer.writerow({
                    "recall_id":           _fmt(r.recall_id),
                    "trigger_batch_id":    _fmt(r.trigger_batch_id),
                    "recalled_batch_ids":  "|".join(r.recalled_batch_ids),
                    "reason":              _fmt(r.reason),
                    "rule_id":             _fmt(r.rule_id),
                    "recalled_at":         _fmt(r.recalled_at),
                })
        return path

    # ------------------------------------------------------------------
    # 5. decision_log.csv
    # ------------------------------------------------------------------

    def write_decision_log(self, decisions: List[BatchDecision]) -> str:
        """Write decision_log.csv (chronological log of all decisions).

        Returns:
            Absolute path to the written file.
        """
        path = os.path.join(self._output_dir, "decision_log.csv")
        fieldnames = [
            "sequence", "recorded_at", "batch_id", "decision",
            "decision_reason", "rule_ids", "is_late",
        ]
        sorted_decisions = sorted(decisions, key=lambda d: d.recorded_at)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for i, d in enumerate(sorted_decisions, start=1):
                writer.writerow({
                    "sequence":        i,
                    "recorded_at":     _fmt(d.recorded_at),
                    "batch_id":        _fmt(d.batch_id),
                    "decision":        _fmt(d.decision),
                    "decision_reason": _fmt(d.decision_reason),
                    "rule_ids":        "|".join(d.rule_ids),
                    "is_late":         _fmt(d.is_late),
                })
        return path

    # ------------------------------------------------------------------
    # Generate all reports at once
    # ------------------------------------------------------------------

    def generate_all(
        self,
        decisions: List[BatchDecision],
        switching_records: List[SwitchingRecord],
        batches: List[Batch],
        recalls: List[RecallRecord],
    ) -> Dict[str, str]:
        """Generate all five standard reports.

        Returns:
            Dict mapping report name -> file path.
        """
        return {
            "batch_decisions":    self.write_batch_decisions(decisions),
            "switching_history":  self.write_switching_history(switching_records),
            "release_register":   self.write_release_register(batches),
            "recall_register":    self.write_recall_register(recalls),
            "decision_log":       self.write_decision_log(decisions),
        }


