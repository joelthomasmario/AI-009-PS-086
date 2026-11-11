"""
command_parser.py – CSV command-file parser and dispatcher.

Shared module – AI-009
Team: AI-009  Section: 6BTAI

Command CSV format:
    command, [field1, field2, ...]

Each row in the CSV file represents one command. The first column is always
'command'. Subsequent columns carry command-specific parameters.

Supported commands:
  REGISTER_PRODUCT, REGISTER_SUPPLIER, REGISTER_LINE, CREATE_BATCH,
  BEGIN_INSPECTION, RECORD_RESULT, REWORK, RELEASE, HOLD,
  CORRECTIVE_ACTION, COMPLAINT, RECALL
"""

from __future__ import annotations

import csv
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    Batch,
    BatchState,
    CorrectiveAction,
    CustomerComplaint,
    DefectClass,
    DefectClassConfig,
    InspectionSeverity,
    ProductionLine,
    RecallRecord,
    Supplier,
    BatchDecision,
)
from .inspection_engine import InspectionEngine
from .product_service import ProductService
from .supplier_service import SupplierService
from .validation import (
    ValidationError,
    require_choice,
    require_datetime,
    require_id,
    require_non_empty,
    require_non_negative_int,
    require_positive_int,
    validate_command_fields,
)


class CommandResult:
    """Result of processing a single command."""

    def __init__(
        self,
        row_num: int,
        command: str,
        success: bool,
        message: str,
        data: Optional[Any] = None,
    ) -> None:
        self.row_num = row_num
        self.command = command
        self.success = success
        self.message = message
        self.data = data

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"Row {self.row_num} [{status}] {self.command}: {self.message}"


class CommandParser:
    """Reads and processes a command CSV file, dispatching each row to the
    appropriate engine methods.

    Shared module – AI-009

    Args:
        engine: InspectionEngine instance.
        product_svc: ProductService instance.
        supplier_svc: SupplierService instance.
        batch_store: Mutable dict mapping batch_id -> Batch.
        decision_log: Mutable list to append BatchDecision records.
        switching_log: Mutable list to append SwitchingRecord objects.
        recall_log: Mutable list to append RecallRecord objects.
    """

    def __init__(
        self,
        engine: InspectionEngine,
        product_svc: ProductService,
        supplier_svc: SupplierService,
        batch_store: Dict[str, Batch],
        decision_log: List[BatchDecision],
        switching_log: List,
        recall_log: List[RecallRecord],
    ) -> None:
        self._engine = engine
        self._products = product_svc
        self._suppliers = supplier_svc
        self._batches = batch_store
        self._decisions = decision_log
        self._switching = switching_log
        self._recalls = recall_log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_file(self, csv_path: str) -> List[CommandResult]:
        """Process all commands in a CSV file.

        Args:
            csv_path: Path to the command CSV file.

        Returns:
            List of CommandResult objects, one per row.

        Raises:
            FileNotFoundError: If csv_path does not exist.
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Command file not found: {csv_path}")

        results: List[CommandResult] = []
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise ValueError(f"Command file {csv_path} is empty or has no header.")
            norm_headers = [h.strip().lower() for h in reader.fieldnames]
            if "command" not in norm_headers:
                raise ValueError(
                    f"Command file {csv_path} must have a 'command' column."
                )

            for row_num, raw_row in enumerate(reader, start=2):
                row = {k.strip().lower(): (v.strip() if v is not None else "") for k, v in raw_row.items() if k}
                command = row.get("command", "").upper().strip()
                if not command:
                    results.append(CommandResult(row_num, "", False, "Empty command; row skipped."))
                    continue

                result = self._dispatch(row_num, command, row)
                results.append(result)

        return results

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, row_num: int, command: str, row: Dict[str, str]) -> CommandResult:
        handlers = {
            "REGISTER_PRODUCT":  self._cmd_register_product,
            "REGISTER_SUPPLIER": self._cmd_register_supplier,
            "REGISTER_LINE":     self._cmd_register_line,
            "CREATE_BATCH":      self._cmd_create_batch,
            "BEGIN_INSPECTION":  self._cmd_begin_inspection,
            "RECORD_RESULT":     self._cmd_record_result,
            "REWORK":            self._cmd_rework,
            "RELEASE":           self._cmd_release,
            "HOLD":              self._cmd_hold,
            "CORRECTIVE_ACTION": self._cmd_corrective_action,
            "COMPLAINT":         self._cmd_complaint,
            "RECALL":            self._cmd_recall,
        }

        handler = handlers.get(command)
        if handler is None:
            return CommandResult(
                row_num, command, False,
                f"Unknown command '{command}'. "
                f"Valid commands: {sorted(handlers.keys())}"
            )

        try:
            msg, data = handler(row)
            return CommandResult(row_num, command, True, msg, data)
        except (ValidationError, ValueError, KeyError, PermissionError, FileNotFoundError) as exc:
            return CommandResult(row_num, command, False, str(exc))

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_register_product(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("REGISTER_PRODUCT", row, ["product_id", "name"])
        pid = require_id(row["product_id"], "product_id")
        name = require_non_empty(row["name"], "name")
        shelf_life = int(row.get("total_shelf_life_days", "0") or "0")

        product = self._products.register(pid, name, total_shelf_life_days=shelf_life)
        return f"Product '{pid}' registered: {name}", product

    def _cmd_register_supplier(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("REGISTER_SUPPLIER", row, ["supplier_id", "name"])
        sid = require_id(row["supplier_id"], "supplier_id")
        name = require_non_empty(row["name"], "name")
        supplier = self._suppliers.register_supplier(sid, name)
        return f"Supplier '{sid}' registered: {name}", supplier

    def _cmd_register_line(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("REGISTER_LINE", row, ["line_id", "name"])
        lid = require_id(row["line_id"], "line_id")
        name = require_non_empty(row["name"], "name")
        line = self._suppliers.register_line(lid, name)
        return f"Production line '{lid}' registered: {name}", line

    def _cmd_create_batch(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields(
            "CREATE_BATCH", row,
            ["batch_id", "product_id", "source_id", "source_type", "lot_size", "raw_material_lot_id", "manufacture_date"]
        )
        bid = require_id(row["batch_id"], "batch_id")
        if bid in self._batches:
            raise ValueError(f"Batch '{bid}' already exists.")
        pid = require_id(row["product_id"], "product_id")
        self._products.get(pid)  # validate exists

        sid = require_id(row["source_id"], "source_id")
        stype = require_choice(row["source_type"], "source_type", ["SUPPLIER", "LINE"])
        self._suppliers.get_source(sid, stype)  # validate exists

        lot_size = require_positive_int(row["lot_size"], "lot_size")
        raw_lot = require_id(row["raw_material_lot_id"], "raw_material_lot_id")
        mfg_date = require_datetime(row["manufacture_date"], "manufacture_date")

        expiry_date: Optional[datetime] = None
        if row.get("expiry_date", "").strip():
            expiry_date = require_datetime(row["expiry_date"], "expiry_date")

        product = self._products.get(pid)
        batch = Batch(
            batch_id=bid,
            product_id=pid,
            source_id=sid,
            source_type=stype,
            lot_size=lot_size,
            raw_material_lot_id=raw_lot,
            manufacture_date=mfg_date,
            expiry_date=expiry_date,
            total_shelf_life_days=product.total_shelf_life_days,
        )
        self._batches[bid] = batch
        return f"Batch '{bid}' created (lot_size={lot_size})", batch

    def _cmd_begin_inspection(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("BEGIN_INSPECTION", row, ["batch_id"])
        bid = require_id(row["batch_id"], "batch_id")
        batch = self._get_batch(bid)

        source = self._get_source_for_batch(batch)
        ts = None
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        if batch.state == BatchState.ON_HOLD:
            # BR-08: ON_HOLD reinspection — transitions ON_HOLD -> UNDER_INSPECTION
            # and sets batch.hold_reinspection = True for double sample size
            self._engine.begin_hold_inspection(batch, source, ts)
            return (
                f"Batch '{bid}' (ON_HOLD) moved to UNDER_INSPECTION for reinspection "
                f"at double sample size (BR-08)",
                batch,
            )

        # Normal flow: QUARANTINE -> UNDER_INSPECTION
        self._engine.begin_inspection(batch, source, ts)
        return f"Batch '{bid}' moved to UNDER_INSPECTION", batch

    def _cmd_record_result(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields(
            "RECORD_RESULT", row,
            ["batch_id", "critical", "major", "minor", "sampled_at"]
        )
        bid = require_id(row["batch_id"], "batch_id")
        batch = self._get_batch(bid)
        source = self._get_source_for_batch(batch)
        product = self._products.get(batch.product_id)

        defects = {
            DefectClass.CRITICAL: require_non_negative_int(row["critical"], "critical"),
            DefectClass.MAJOR:    require_non_negative_int(row["major"], "major"),
            DefectClass.MINOR:    require_non_negative_int(row["minor"], "minor"),
        }
        sampled_at = require_datetime(row["sampled_at"], "sampled_at")
        recorded_at: Optional[datetime] = None
        if row.get("recorded_at", "").strip():
            recorded_at = require_datetime(row["recorded_at"], "recorded_at")

        rework_round = int(row.get("rework_round", "0") or "0")

        # BR-08/BR-09: Capture hold reinspection flag BEFORE record_result resets it
        was_hold_reinspection = batch.hold_reinspection

        decision, sw_records = self._engine.record_result(
            batch=batch,
            source=source,
            defect_configs=product.defect_configs,
            defects=defects,
            sampled_at=sampled_at,
            recorded_at=recorded_at,
            rework_round=rework_round,
        )
        self._decisions.append(decision)
        self._switching.extend(sw_records)

        # Apply decision to batch lifecycle
        self._engine.apply_decision(batch, decision, recorded_at)

        # BR-09: Critical defect during ON_HOLD reinspection -> recall cascade
        if was_hold_reinspection and decision.defects.get(DefectClass.CRITICAL, 0) > 0:
            recall = self._engine.trigger_recall(
                list(self._batches.values()), batch,
                "Critical defect found during ON_HOLD reinspection (BR-09)",
                recorded_at,
            )
            self._recalls.append(recall)
            return (
                f"Batch '{bid}': {decision.decision.value}. "
                f"RECALL triggered for lot {batch.raw_material_lot_id}.",
                (decision, recall),
            )

        return f"Batch '{bid}': {decision.decision.value}. {decision.decision_reason}", decision

    def _cmd_rework(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("REWORK", row, ["batch_id"])
        bid = require_id(row["batch_id"], "batch_id")
        batch = self._get_batch(bid)

        # Retrieve the MAJOR Re from the last sampling plan evaluation
        last_decision = self._get_last_decision(bid)
        major_re = 0
        if last_decision:
            major_re = last_decision.re_values.get(DefectClass.MAJOR, 0)

        ts = None
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        success, reason = self._engine.begin_rework(batch, major_re, ts)
        if not success:
            raise ValueError(f"Rework not permitted for batch '{bid}': {reason}")

        # Immediately move to UNDER_INSPECTION for reinspection
        self._engine.begin_reinspection(batch, ts)
        return f"Batch '{bid}' rework started; now UNDER_INSPECTION at TIGHTENED.", batch

    def _cmd_release(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("RELEASE", row, ["batch_id"])
        bid = require_id(row["batch_id"], "batch_id")
        batch = self._get_batch(bid)
        ts = None
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        # Allow releasing from UNDER_INSPECTION state too (manual override)
        if batch.state not in (BatchState.UNDER_INSPECTION, BatchState.ON_HOLD):
            raise ValueError(
                f"Batch '{bid}' cannot be released from state {batch.state.value}."
            )

        success, code, reason = self._engine._lifecycle.try_release(batch, ts)
        if not success:
            return f"Batch '{bid}' rejected: {reason}", batch
        return f"Batch '{bid}' RELEASED. {reason}", batch

    def _cmd_hold(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("HOLD", row, ["batch_id", "reason"])
        bid = require_id(row["batch_id"], "batch_id")
        batch = self._get_batch(bid)
        reason = require_non_empty(row["reason"], "reason")

        ts = None
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        success, msg = self._engine.place_on_hold(batch, reason, ts)
        if not success:
            raise ValueError(f"Cannot place batch '{bid}' on hold: {msg}")
        return f"Batch '{bid}' placed ON_HOLD. {msg}", batch

    def _cmd_corrective_action(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("CORRECTIVE_ACTION", row, ["action_id", "source_id", "description"])
        aid = require_id(row["action_id"], "action_id")
        sid = require_id(row["source_id"], "source_id")
        desc = require_non_empty(row["description"], "description")

        ts = datetime.utcnow()
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        # Find the source (supplier or line)
        source: Union[Supplier, ProductionLine, None] = None
        if self._suppliers.supplier_exists(sid):
            source = self._suppliers.get_supplier(sid)
        elif self._suppliers.line_exists(sid):
            source = self._suppliers.get_line(sid)
        else:
            raise KeyError(f"Source '{sid}' not found as supplier or production line.")

        action = CorrectiveAction(action_id=aid, source_id=sid, description=desc, registered_at=ts)
        self._engine.register_corrective_action(source, action)
        return (
            f"Corrective action '{aid}' registered for '{sid}'. "
            f"Severity switched from DISCONTINUED to TIGHTENED (BR-06).",
            action,
        )

    def _cmd_complaint(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("COMPLAINT", row, ["complaint_id", "batch_id", "description"])
        cid = require_id(row["complaint_id"], "complaint_id")
        bid = require_id(row["batch_id"], "batch_id")
        desc = require_non_empty(row["description"], "description")

        ts = datetime.utcnow()
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        batch = self._get_batch(bid)
        complaint = CustomerComplaint(
            complaint_id=cid, batch_id=bid, description=desc, filed_at=ts
        )

        # Trigger recall (BR-09)
        recall = self._engine.trigger_recall(
            list(self._batches.values()), batch,
            f"Customer complaint {cid}: {desc}",
            ts,
        )
        self._recalls.append(recall)
        return (
            f"Complaint '{cid}' filed; recall triggered for batch '{bid}' "
            f"and lot '{batch.raw_material_lot_id}'. "
            f"Recalled {len(recall.recalled_batch_ids)} batch(es).",
            (complaint, recall),
        )

    def _cmd_recall(self, row: Dict[str, str]) -> Tuple[str, Any]:
        validate_command_fields("RECALL", row, ["batch_id", "reason"])
        bid = require_id(row["batch_id"], "batch_id")
        reason = require_non_empty(row["reason"], "reason")
        batch = self._get_batch(bid)

        ts = None
        if row.get("timestamp", "").strip():
            ts = require_datetime(row["timestamp"], "timestamp")

        recall = self._engine.trigger_recall(
            list(self._batches.values()), batch, reason, ts
        )
        self._recalls.append(recall)
        return (
            f"Recall triggered for batch '{bid}'. "
            f"{len(recall.recalled_batch_ids)} batch(es) recalled.",
            recall,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_batch(self, batch_id: str) -> Batch:
        if batch_id not in self._batches:
            raise KeyError(f"Batch '{batch_id}' not found.")
        return self._batches[batch_id]

    def _get_source_for_batch(self, batch: Batch) -> Union[Supplier, ProductionLine]:
        return self._suppliers.get_source(batch.source_id, batch.source_type)

    def _get_last_decision(self, batch_id: str) -> Optional[BatchDecision]:
        """Return the most recent BatchDecision for a given batch_id."""
        matches = [d for d in self._decisions if d.batch_id == batch_id]
        if not matches:
            return None
        return max(matches, key=lambda d: d.recorded_at)


