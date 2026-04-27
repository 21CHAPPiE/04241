from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

repo_root_text = str(REPO_ROOT)
if sys.path[0] != repo_root_text:
    try:
        sys.path.remove(repo_root_text)
    except ValueError:
        pass
    sys.path.insert(0, repo_root_text)

for module_name in list(sys.modules):
    if not (module_name == "project" or module_name.startswith("project.")):
        continue
    module = sys.modules.get(module_name)
    module_file = getattr(module, "__file__", None)
    if module_file is None:
        continue
    if not str(module_file).startswith(repo_root_text):
        del sys.modules[module_name]

project_init = REPO_ROOT / "project" / "__init__.py"
spec = importlib.util.spec_from_file_location(
    "project",
    project_init,
    submodule_search_locations=[str(REPO_ROOT / "project"), repo_root_text],
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to prepare project package from {project_init}")
project_module = importlib.util.module_from_spec(spec)
sys.modules["project"] = project_module
spec.loader.exec_module(project_module)
