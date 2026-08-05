"""Pytest configuration: ensure the project root is importable."""

import os
import sys

# Add the repository root so `import wol_app` works regardless of CWD
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
