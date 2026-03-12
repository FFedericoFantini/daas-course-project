import sys
from pathlib import Path

shared_root = Path(__file__).resolve().parent / "packages" / "shared"
shared_root_str = str(shared_root)

if shared_root.exists() and shared_root_str not in sys.path:
    sys.path.insert(0, shared_root_str)
