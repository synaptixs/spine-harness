"""Locations shared by source checkouts and portable archives."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
CONSTITUTION = PACKAGE_DIR / "data" / "constitution.md"
