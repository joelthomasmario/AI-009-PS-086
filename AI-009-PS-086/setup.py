"""
setup.py – Package setup for the AQL Engine.

Team AI-009 | PS-086 | Section 6BTAI
"""

from setuptools import setup, find_packages

setup(
    name="aql-engine",
    version="1.0.0",
    description="AQL Sampling, Inspection Severity and Batch Release Engine",
    author="AI-009 Team – Joel Thomas Mario J, Joselet K Jaison, Joseph Mangaly",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],  # No external dependencies required
    extras_require={
        "test": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "aql-engine=src.main:main",
        ],
    },
)

