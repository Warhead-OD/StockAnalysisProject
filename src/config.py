"""
Configuration and constants.

This file can hold API keys, cache directories, default settings, etc.
"""

from pathlib import Path

# Cache directory for yfinance data
CACHE_DIR = Path.home() / ".cache" / "claude-stock"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Project-local artifact directories
DOWNLOADS_DIR = Path("downloads")
MARKET_DATA_DIR = DOWNLOADS_DIR / "market"
METADATA_DIR = DOWNLOADS_DIR / "meta"
OUTPUTS_DIR = Path("outputs")

MARKET_DATA_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
