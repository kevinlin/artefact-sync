"""Entry point. Running this file puts its own directory on sys.path, so no PYTHONPATH is needed."""

from __future__ import annotations

from cli import main

raise SystemExit(main())
