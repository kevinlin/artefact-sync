"""Test package. Puts the skill's `scripts/` on the path, the way running a script there does."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
