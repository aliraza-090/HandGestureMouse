"""HandGestureMouse entry point.

Run from the project root:

    python main.py

This module makes the ``src`` layout importable when the package is launched
from a source checkout.
"""

import os
import sys


def _bootstrap() -> None:
    """Put ``src`` on sys.path so ``handgesturemouse`` resolves."""
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


if __name__ == "__main__":
    _bootstrap()
    from handgesturemouse.app import main

    main()