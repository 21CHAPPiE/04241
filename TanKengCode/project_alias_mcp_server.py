from __future__ import annotations

import sys
import types
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parent
    pkg = types.ModuleType("project")
    pkg.__path__ = [str(repo)]
    pkg.__file__ = str(repo / "__init__.py")
    sys.modules["project"] = pkg

    from project.tanken_mcp_server import main as server_main

    return int(server_main())


if __name__ == "__main__":
    raise SystemExit(main())
