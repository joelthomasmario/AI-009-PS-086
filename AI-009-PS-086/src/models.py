"""
models.py - Core data models for the AQL Sampling, Inspection Severity
and Batch Release Engine.

Module Owner: Joel Thomas Mario J (2463029) – sampling/defect models
              Joseph Mangaly (2463031) – lifecycle/batch models
              Joselet K Jaison (2463030) – supplier/switching models

Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class InspectionSeverity(str, enum.Enum):
    """Inspection severity levels (BR-04, BR-05, BR-06)."""
    NORMAL = "NORMAL"
    TIGHTENED = "TIGHTENED"
    REDUCED = "REDUCED"
    DISCONTINUED = "DISCONTINUED"


class BatchState(str, enum.Enum):
    """Legal batch lifecycle states (Section 6)."""
    QUARANTINE = "QUARANTINE"
    UNDER_INSPECTION = "UNDER_INSPECTION"
    RELEASED = "RELEASED"
    ON_HOLD = "ON_HOLD"
    REJECTED = "REJECTED"
    REWORK = "REWORK"
    RECALLED = "RECALLED"


class DefectClass(str, enum.Enum):
    """Defect classification levels (BR-02)."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class DecisionCode(str, enum.Enum):
    """Standardised decision codes attached to batch decisions."""
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REJECTED_CRITICAL = "REJECTED_CRITICAL"
    REJECTED_SHORT_DATED = "REJECTED_SHORT_DATED"  # BR-10
    ACCEPTED_SWITCH_TO_NORMAL = "ACCEPTED_SWITCH_TO_NORMAL"  # BR-05
    REWORK_ELIGIBLE = "REWORK_ELIGIBLE"
    REWORK_FINAL_REJECTION = "REWORK_FINAL_REJECTION"
    RELEASED = "RELEASED"
    ON_HOLD = "ON_HOLD"
    RECALLED = "RECALLED"
    LATE_RESULT = "LATE_RESULT"  # BR-11


# ---------------------------------------------------------------------------
# Sampling / Defect Models  (Joel Thomas Mario J – 2463029)
# ---------------------------------------------------------------------------

@dataclass
class SamplingPlanEntry:
    """One row from the AQL sampling plan CSV.

    Attributes:
        code_letter: ISO 2859-1 sample-size code letter (A-R).
        aql: Acceptable Quality Level (e.g. 0.065, 1.0, 2.5, 4.0 …).
        severity: InspectionSeverity for this entry.
        sample_size: Number of units to inspect (n).
        ac: Acceptance number.
        re: Rejection number.
    """
    code_letter: str
    aql: float
    severity: InspectionSeverity
    sample_size: int
    ac: int
    re: int

    def __post_init__(self) -> None:
        if self.sample_size < 1:
            raise ValueError(f"sample_size must be >= 1, got {self.sample_size}")
        if self.re <= self.ac:
            raise ValueError(
                f"re ({self.re}) must be > ac ({self.ac}) for letter={self.code_letter}"
            )


@dataclass
class DefectClassConfig:
    """AQL assignment per defect class (BR-02).

    Attributes:
        defect_class: CRITICAL / MAJOR / MINOR.
        aql: AQL value associated with this class for sampling plan lookup.
    """
    defect_class: DefectClass
    aql: float

    # Default AQL values per BR-02
    _DEFAULTS: Dict[DefectClass, float] = field(
        default_factory=lambda: {
            DefectClass.CRITICAL: 0.065,
            DefectClass.MAJOR: 1.0,
            DefectClass.MINOR: 2.5,
        },
        repr=False,
    )

    @classmethod
    def defaults(cls) -> List["DefectClassConfig"]:
        """Return the three default defect-class configurations (BR-02)."""
        return [
            cls(DefectClass.CRITICAL, 0.065),
            cls(DefectClass.MAJOR, 1.0),
            cls(DefectClass.MINOR, 2.5),
        ]


@dataclass
class InspectionResult:
    """Record of defects found during one inspection.

    Attributes:
        batch_id: Batch being inspected.
        sample_size: Actual units inspected.
        defects: Mapping from DefectClass to count.
        sampled_at: When sampling was performed.
        recorded_at: When the result was entered into the system.
        is_late: True if recorded more than 48 hours after sampling (BR-11).
        rework_round: 0 for original inspection, 1 for rework reinspection.
    """
    batch_id: str
    sample_size: int
    defects: Dict[DefectClass, int]
    sampled_at: datetime
    recorded_at: datetime
    is_late: bool = False
    rework_round: int = 0
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def total_defects(self) -> int:
        return sum(self.defects.values())

    def defects_for(self, cls: DefectClass) -> int:
        return self.defects.get(cls, 0)


# ---------------------------------------------------------------------------
# Product & Supplier Models  (Joselet K Jaison – 2463030 / Joel 2463029)
# ---------------------------------------------------------------------------

@dataclass
class Product:
    """A registered product with its defect-class configuration.

    Attributes:
        product_id: Unique identifier.
        name: Human-readable name.
        defect_configs: Per-class AQL configuration.
        total_shelf_life_days: Total shelf life in days (for BR-10).
    """
    product_id: str
    name: str
    defect_configs: List[DefectClassConfig] = field(default_factory=DefectClassConfig.defaults)
    total_shelf_life_days: int = 0  # 0 means no shelf-life check

    def get_aql(self, defect_class: DefectClass) -> float:
        for dc in self.defect_configs:
            if dc.defect_class == defect_class:
                return dc.aql
        raise ValueError(f"No AQL configured for {defect_class} in product {self.product_id}")


@dataclass
class SwitchingRecord:
    """One severity-switching event (BR-04 / BR-05 / BR-06).

    Attributes:
        source_id: Supplier or production-line ID.
        previous_severity: Before the switch.
        new_severity: After the switch.
        triggering_batch_id: Batch that triggered the switch.
        rule_id: Business rule identifier (e.g. 'BR-04').
        event: Short human-readable description.
        timestamp: When the switch occurred.
    """
    source_id: str
    previous_severity: InspectionSeverity
    new_severity: InspectionSeverity
    triggering_batch_id: str
    rule_id: str
    event: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Supplier:
    """A registered supplier with current severity and inspection history.

    Attributes:
        supplier_id: Unique identifier.
        name: Company name.
        severity: Current InspectionSeverity (Joselet K Jaison – 2463030).
        consecutive_accepts: Counter for NORMAL->REDUCED or TIGHTENED->NORMAL.
        consecutive_rejects_in_window: Maintained externally by switching_engine.
        tightened_reject_count: Cumulative rejections while TIGHTENED (BR-04).
        last_inspection_at: Timestamp of most recent inspection.
        corrective_action_registered: Required before resuming from DISCONTINUED.
        switching_history: Log of all severity changes.
    """
    supplier_id: str
    name: str
    severity: InspectionSeverity = InspectionSeverity.NORMAL
    consecutive_accepts: int = 0
    tightened_reject_count: int = 0
    last_inspection_at: Optional[datetime] = None
    corrective_action_registered: bool = False
    switching_history: List[SwitchingRecord] = field(default_factory=list)
    # Last-5-batch decision window for switching (BR-04): list of bool (True=accept)
    recent_decisions: List[bool] = field(default_factory=list)


@dataclass
class ProductionLine:
    """A registered production line – same switching semantics as Supplier.

    Joselet K Jaison – 2463030
    """
    line_id: str
    name: str
    severity: InspectionSeverity = InspectionSeverity.NORMAL
    consecutive_accepts: int = 0
    tightened_reject_count: int = 0
    last_inspection_at: Optional[datetime] = None
    corrective_action_registered: bool = False
    switching_history: List[SwitchingRecord] = field(default_factory=list)
    recent_decisions: List[bool] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Batch Model  (Joseph Mangaly – 2463031)
# ---------------------------------------------------------------------------

# Legal state transitions (Section 6 + BR-08 ON_HOLD reinspection)
LEGAL_TRANSITIONS: Dict[BatchState, List[BatchState]] = {
    BatchState.QUARANTINE:        [BatchState.UNDER_INSPECTION],
    BatchState.UNDER_INSPECTION:  [BatchState.ON_HOLD, BatchState.RELEASED, BatchState.REJECTED],
    BatchState.RELEASED:          [BatchState.ON_HOLD, BatchState.RECALLED],
    # ON_HOLD -> UNDER_INSPECTION added for BR-08 reinspection at double sample size
    BatchState.ON_HOLD:           [BatchState.UNDER_INSPECTION, BatchState.RELEASED,
                                   BatchState.REJECTED, BatchState.RECALLED],
    BatchState.REJECTED:          [BatchState.REWORK],
    BatchState.REWORK:            [BatchState.UNDER_INSPECTION],
    BatchState.RECALLED:          [],  # terminal
}


@dataclass
class Batch:
    """Represents one production or receiving batch.

    Joseph Mangaly – 2463031

    Attributes:
        batch_id: Unique batch identifier.
        product_id: Associated product.
        source_id: Supplier or production-line ID.
        source_type: 'SUPPLIER' or 'LINE'.
        lot_size: Total units in the lot.
        raw_material_lot_id: Shared lot identifier for hold/recall cascade.
        manufacture_date: Date of manufacture.
        expiry_date: Date of expiry (for shelf-life check BR-10 and recall cascade BR-09).
        state: Current lifecycle state.
        created_at: When the batch was registered.
        released_at: Timestamp of RELEASED transition (for hold window BR-08).
        rework_count: Number of rework cycles applied (max 1 per BR-07).
        rejection_reason: Last rejection reason code.
        is_short_dated: Set True if rejected due to shelf life (BR-10).
        total_shelf_life_days: Copied from product at creation for self-contained checks.
        inspection_results: All inspection results recorded for this batch.
        state_history: Ordered list of (state, timestamp, reason) tuples.
    """
    batch_id: str
    product_id: str
    source_id: str
    source_type: str  # 'SUPPLIER' or 'LINE'
    lot_size: int
    raw_material_lot_id: str
    manufacture_date: datetime
    expiry_date: Optional[datetime] = None
    state: BatchState = BatchState.QUARANTINE
    created_at: datetime = field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = None
    rework_count: int = 0
    rejection_reason: Optional[str] = None
    is_short_dated: bool = False
    total_shelf_life_days: int = 0
    # BR-08: Set True when ON_HOLD batch transitions to UNDER_INSPECTION for reinspection.
    # Signals double sample size requirement. Reset by InspectionEngine.record_result().
    hold_reinspection: bool = False
    inspection_results: List[InspectionResult] = field(default_factory=list)
    state_history: List[tuple] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.state_history.append((self.state, self.created_at, "BATCH_CREATED"))

    def transition_to(self, new_state: BatchState, reason: str = "", timestamp: Optional[datetime] = None) -> None:
        """Perform a validated state transition.

        Raises:
            ValueError: If the transition is not permitted by LEGAL_TRANSITIONS.
        """
        allowed = LEGAL_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Illegal transition for batch {self.batch_id}: "
                f"{self.state.value} -> {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.state = new_state
        ts = timestamp or datetime.utcnow()
        if new_state == BatchState.RELEASED:
            self.released_at = ts
        self.state_history.append((new_state, ts, reason))

    def remaining_shelf_life_days(self, as_of: Optional[datetime] = None) -> Optional[float]:
        """Return remaining shelf life in days, or None if no expiry set."""
        if self.expiry_date is None:
            return None
        ref = as_of or datetime.utcnow()
        return (self.expiry_date - ref).total_seconds() / 86400.0

    def shelf_life_ratio(self, as_of: Optional[datetime] = None) -> Optional[float]:
        """Return remaining_shelf_life / total_shelf_life, or None if not applicable."""
        if self.total_shelf_life_days == 0 or self.expiry_date is None:
            return None
        remaining = self.remaining_shelf_life_days(as_of)
        if remaining is None:
            return None
        return remaining / self.total_shelf_life_days

    @property
    def latest_result(self) -> Optional[InspectionResult]:
        """Return the most recently recorded inspection result."""
        if not self.inspection_results:
            return None
        return max(self.inspection_results, key=lambda r: r.recorded_at)


# ---------------------------------------------------------------------------
# Decision Record (shared output model)
# ---------------------------------------------------------------------------

@dataclass
class BatchDecision:
    """Full decision record for one inspection event.

    Shared module – used by report_generator.py
    """
    batch_id: str
    product_id: str
    source_id: str
    lot_size: int
    code_letter: str
    severity: InspectionSeverity
    sample_size: int
    defects: Dict[DefectClass, int]
    ac_values: Dict[DefectClass, int]        # per-class Ac
    re_values: Dict[DefectClass, int]        # per-class Re
    decision: DecisionCode
    decision_reason: str
    rule_ids: List[str]
    sampled_at: datetime
    recorded_at: datetime
    is_late: bool
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class CorrectiveAction:
    """Corrective action record (BR-06).

    Attributes:
        action_id: Unique identifier.
        source_id: Supplier or production-line ID.
        description: Description of corrective measure taken.
        registered_at: Timestamp of registration.
    """
    action_id: str
    source_id: str
    description: str
    registered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CustomerComplaint:
    """Customer complaint triggering recall (BR-09).

    Attributes:
        complaint_id: Unique identifier.
        batch_id: Batch cited by the complaint.
        description: Complaint description.
        filed_at: Timestamp.
    """
    complaint_id: str
    batch_id: str
    description: str
    filed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RecallRecord:
    """Record of a recall event (BR-09).

    Attributes:
        recall_id: Unique identifier.
        trigger_batch_id: Batch that initiated the recall.
        recalled_batch_ids: All batches recalled (including cascade).
        reason: Human-readable reason.
        rule_id: 'BR-09'.
        recalled_at: Timestamp.
    """
    recall_id: str
    trigger_batch_id: str
    recalled_batch_ids: List[str]
    reason: str
    rule_id: str = "BR-09"
    recalled_at: datetime = field(default_factory=datetime.utcnow)


