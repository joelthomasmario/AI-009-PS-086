"""
product_service.py – Product and defect-class registration service.

Module Owner: Joel Thomas Mario J (2463029)
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import DefectClass, DefectClassConfig, Product


class ProductService:
    """Manages product registration and retrieval.

    Joel Thomas Mario J – 2463029

    Usage::

        svc = ProductService()
        svc.register("P001", "Widget A", total_shelf_life_days=365)
        product = svc.get("P001")
    """

    def __init__(self) -> None:
        self._products: Dict[str, Product] = {}

    def register(
        self,
        product_id: str,
        name: str,
        total_shelf_life_days: int = 0,
        defect_configs: Optional[List[DefectClassConfig]] = None,
    ) -> Product:
        """Register a new product.

        Args:
            product_id: Unique product identifier.
            name: Human-readable product name.
            total_shelf_life_days: Total shelf life in days (0 = no check).
            defect_configs: Per-class AQL configuration. Defaults to BR-02 defaults.

        Returns:
            The newly created Product.

        Raises:
            ValueError: If the product_id is already registered.
        """
        if product_id in self._products:
            raise ValueError(f"Product '{product_id}' is already registered.")

        configs = defect_configs or DefectClassConfig.defaults()
        product = Product(
            product_id=product_id,
            name=name,
            defect_configs=configs,
            total_shelf_life_days=total_shelf_life_days,
        )
        self._products[product_id] = product
        return product

    def get(self, product_id: str) -> Product:
        """Retrieve a registered product.

        Raises:
            KeyError: If the product_id is not found.
        """
        if product_id not in self._products:
            raise KeyError(f"Product '{product_id}' not found.")
        return self._products[product_id]

    def all_products(self) -> List[Product]:
        return list(self._products.values())

    def exists(self, product_id: str) -> bool:
        return product_id in self._products

