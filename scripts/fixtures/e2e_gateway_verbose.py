#!/usr/bin/env python3
"""Run the production Gateway with INFO lifecycle logs for E2E readiness."""

from __future__ import annotations

import logging

from personal_assistant.main import main


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
