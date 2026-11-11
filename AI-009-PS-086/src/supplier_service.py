"""
supplier_service.py – Supplier and production-line registration service.

Module Owner: Joselet K Jaison (2463030)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

from typing import Dict, List, Union

from .models import InspectionSeverity, ProductionLine, Supplier


class SupplierService:
    """Manages supplier and production-line registration and retrieval.

    Joselet K Jaison – 2463030

    Usage::

        svc = SupplierService()
        svc.register_supplier("S001", "Acme Corp")
        svc.register_line("L001", "Line A")
    """

    def __init__(self) -> None:
        self._suppliers: Dict[str, Supplier] = {}
        self._lines: Dict[str, ProductionLine] = {}

    # ------------------------------------------------------------------
    # Suppliers
    # ------------------------------------------------------------------

    def register_supplier(
        self,
        supplier_id: str,
        name: str,
        initial_severity: InspectionSeverity = InspectionSeverity.NORMAL,
    ) -> Supplier:
        """Register a new supplier.

        Args:
            supplier_id: Unique identifier.
            name: Company name.
            initial_severity: Starting severity level.

        Returns:
            The newly created Supplier.

        Raises:
            ValueError: If the supplier_id is already registered.
        """
        if supplier_id in self._suppliers:
            raise ValueError(f"Supplier '{supplier_id}' is already registered.")
        supplier = Supplier(
            supplier_id=supplier_id,
            name=name,
            severity=initial_severity,
        )
        self._suppliers[supplier_id] = supplier
        return supplier

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Retrieve a registered supplier.

        Raises:
            KeyError: If the supplier_id is not found.
        """
        if supplier_id not in self._suppliers:
            raise KeyError(f"Supplier '{supplier_id}' not found.")
        return self._suppliers[supplier_id]

    def all_suppliers(self) -> List[Supplier]:
        return list(self._suppliers.values())

    def supplier_exists(self, supplier_id: str) -> bool:
        return supplier_id in self._suppliers

    # ------------------------------------------------------------------
    # Production Lines
    # ------------------------------------------------------------------

    def register_line(
        self,
        line_id: str,
        name: str,
        initial_severity: InspectionSeverity = InspectionSeverity.NORMAL,
    ) -> ProductionLine:
        """Register a new production line.

        Args:
            line_id: Unique identifier.
            name: Human-readable line name.
            initial_severity: Starting severity level.

        Returns:
            The newly created ProductionLine.

        Raises:
            ValueError: If the line_id is already registered.
        """
        if line_id in self._lines:
            raise ValueError(f"Production line '{line_id}' is already registered.")
        line = ProductionLine(
            line_id=line_id,
            name=name,
            severity=initial_severity,
        )
        self._lines[line_id] = line
        return line

    def get_line(self, line_id: str) -> ProductionLine:
        """Retrieve a registered production line.

        Raises:
            KeyError: If the line_id is not found.
        """
        if line_id not in self._lines:
            raise KeyError(f"Production line '{line_id}' not found.")
        return self._lines[line_id]

    def all_lines(self) -> List[ProductionLine]:
        return list(self._lines.values())

    def line_exists(self, line_id: str) -> bool:
        return line_id in self._lines

    def get_source(self, source_id: str, source_type: str) -> Union[Supplier, ProductionLine]:
        """Retrieve either a supplier or a production line.

        Args:
            source_id: ID of the supplier or line.
            source_type: 'SUPPLIER' or 'LINE'.

        Returns:
            Supplier or ProductionLine.

        Raises:
            KeyError: If not found.
            ValueError: If source_type is invalid.
        """
        source_type = source_type.upper()
        if source_type == "SUPPLIER":
            return self.get_supplier(source_id)
        elif source_type == "LINE":
            return self.get_line(source_id)
        raise ValueError(f"Unknown source_type '{source_type}'. Must be 'SUPPLIER' or 'LINE'.")

