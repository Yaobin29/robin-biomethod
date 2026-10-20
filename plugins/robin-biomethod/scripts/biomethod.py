#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root / "vendor")]
from biomethod.cli import main
if __name__ == "__main__":
    raise SystemExit(main())
