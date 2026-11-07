"""Convenience entry point for GC-02; all behavior lives in the shared runner."""

import sys
from pathlib import Path
from run import main

if __name__ == "__main__":
    main([str(Path(__file__).parent / "cases/gc02/case.json"), *sys.argv[1:]])
