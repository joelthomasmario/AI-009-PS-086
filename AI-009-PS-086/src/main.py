"""
main.py – Entry point for the AQL Sampling, Inspection Severity
and Batch Release Engine.

Usage:
    python -m src.main --commands <commands.csv> --sampling-plan <plan.csv> [--output <dir>]

Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import argparse
import sys
import os
import io
from typing import Dict, List

# Force UTF-8 output on Windows so Unicode characters in messages render correctly
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .models import Batch, BatchDecision, RecallRecord, SwitchingRecord
from .product_service import ProductService
from .supplier_service import SupplierService
from .sampling_engine import SamplingPlanLoader
from .inspection_engine import InspectionEngine
from .command_parser import CommandParser
from .report_generator import ReportGenerator


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aql-engine",
        description=(
            "AQL Sampling, Inspection Severity and Batch Release Engine\n"
            "Team AI-009 | PS-086 | Section 6BTAI"
        ),
    )
    p.add_argument(
        "--commands", "-c",
        required=True,
        metavar="FILE",
        help="Path to the command CSV file.",
    )
    p.add_argument(
        "--sampling-plan", "-s",
        required=True,
        metavar="FILE",
        help="Path to the AQL sampling plan CSV file.",
    )
    p.add_argument(
        "--output", "-o",
        default="outputs",
        metavar="DIR",
        help="Directory for output reports (default: outputs/).",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each command result to stdout.",
    )
    return p


def run(
    commands_file: str,
    sampling_plan_file: str,
    output_dir: str,
    verbose: bool = False,
) -> int:
    """Main execution function.

    Args:
        commands_file: Path to command CSV.
        sampling_plan_file: Path to sampling plan CSV.
        output_dir: Where to write reports.
        verbose: Whether to print each result.

    Returns:
        Exit code (0 = success, 1 = any command failed).
    """
    print("=" * 70)
    print("AQL Sampling, Inspection Severity and Batch Release Engine")
    print("Team AI-009 | PS-086 | Section 6BTAI")
    print("=" * 70)

    # --- Load sampling plan ---
    try:
        loader = SamplingPlanLoader(sampling_plan_file)
        print(f"[OK] Sampling plan loaded: {len(loader.entries)} entries from '{sampling_plan_file}'")
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] Failed to load sampling plan: {exc}", file=sys.stderr)
        return 1

    # --- Initialise services ---
    product_svc = ProductService()
    supplier_svc = SupplierService()
    engine = InspectionEngine(loader)

    batch_store: Dict[str, Batch] = {}
    decision_log: List[BatchDecision] = []
    switching_log: List[SwitchingRecord] = []
    recall_log: List[RecallRecord] = []

    parser = CommandParser(
        engine=engine,
        product_svc=product_svc,
        supplier_svc=supplier_svc,
        batch_store=batch_store,
        decision_log=decision_log,
        switching_log=switching_log,
        recall_log=recall_log,
    )

    # --- Process commands ---
    try:
        results = parser.process_file(commands_file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] Failed to process command file: {exc}", file=sys.stderr)
        return 1

    failures = 0
    for result in results:
        if verbose or not result.success:
            status = "[OK  ]" if result.success else "[FAIL]"
            print(f"  {status} Row {result.row_num:>4} {result.command:<20} {result.message}")
        if not result.success:
            failures += 1

    print(f"\nCommands processed: {len(results)} total, {failures} failed.")

    # --- Generate reports ---
    reporter = ReportGenerator(output_dir)
    report_paths = reporter.generate_all(
        decisions=decision_log,
        switching_records=switching_log,
        batches=list(batch_store.values()),
        recalls=recall_log,
    )

    print("\nReports written:")
    for name, path in report_paths.items():
        print(f"  {name:<25} -> {path}")

    print("\n" + "=" * 70)
    if failures == 0:
        print("All commands completed successfully.")
        return 0
    else:
        print(f"WARNING: {failures} command(s) failed. Review output above.")
        return 1


def main() -> None:
    args = build_arg_parser().parse_args()
    exit_code = run(
        commands_file=args.commands,
        sampling_plan_file=args.sampling_plan,
        output_dir=args.output,
        verbose=args.verbose,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

