from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_DIR = Path(__file__).resolve().parent

__path__ = [str(_PACKAGE_DIR), str(_REPO_ROOT)]
