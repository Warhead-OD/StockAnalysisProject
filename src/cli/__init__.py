"""
CLI package entry points.
"""

from __future__ import annotations

from typing import Sequence

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> None:
    # Lazy import avoids loading src.cli.main during package import.
    from .main import main as _main

    _main(list(argv) if argv is not None else None)


if __name__ == "__main__":
    main()
