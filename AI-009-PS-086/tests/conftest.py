"""
conftest.py – Shared pytest fixtures for the AQL Engine test suite.

Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import os
import pytest
from datetime import datetime

from src.sampling_engine import SamplingPlanLoader
from src.inspection_engine import InspectionEngine
from src.product_service import ProductService
from src.supplier_service import SupplierService
from src.models import (
    DefectClass,
    DefectClassConfig,
    InspectionSeverity,
)

# Absolute path to the shared sampling plan CSV
SAMPLING_PLAN_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "sampling_plan.csv"
)


@pytest.fixture(scope="session")
def plan_loader() -> SamplingPlanLoader:
    """Load the sampling plan once per session."""
    return SamplingPlanLoader(SAMPLING_PLAN_CSV)


@pytest.fixture(scope="session")
def engine(plan_loader) -> InspectionEngine:
    """Single InspectionEngine per session."""
    return InspectionEngine(plan_loader)


@pytest.fixture
def product_svc() -> ProductService:
    return ProductService()


@pytest.fixture
def supplier_svc() -> SupplierService:
    return SupplierService()


@pytest.fixture
def default_defect_configs():
    """Default defect class configs per BR-02."""
    return DefectClassConfig.defaults()


@pytest.fixture
def ts_base() -> datetime:
    """A fixed base timestamp for deterministic tests."""
    return datetime(2026, 1, 15, 10, 0, 0)


def make_defects(critical=0, major=0, minor=0):
    """Helper to create a defects dict."""
    return {
        DefectClass.CRITICAL: critical,
        DefectClass.MAJOR: major,
        DefectClass.MINOR: minor,
    }

