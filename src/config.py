"""Configuration and constants.

This file can hold API keys, cache directories, default settings, etc.
"""

from pathlib import Path

# Cache directory for yfinance data
CACHE_DIR = Path.home() / ".cache" / "claude-stock"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
