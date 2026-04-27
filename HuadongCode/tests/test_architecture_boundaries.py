"""Architecture guard tests for service/core separation intent."""

from __future__ import annotations

import ast
from pathlib import Path


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.name != "__init__.py")


def _imported_modules(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(file_path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def _has_forbidden_import(modules: set[str], forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(
        imported == prefix or imported.startswith(f"{prefix}.")
        for imported in modules
        for prefix in forbidden_prefixes
    )


def test_core_modules_do_not_depend_on_service_or_router_layers(project_root: Path) -> None:
    """Core modules should remain independent from service/router layers."""
    core_files = _python_files(project_root / "app" / "core")
    forbidden = ("app.services", "app.routers", "fastapi")

    violating = []
    for file_path in core_files:
        modules = _imported_modules(file_path)
        if _has_forbidden_import(modules, forbidden):
            violating.append(str(file_path.relative_to(project_root)))

    assert not violating, f"Core import boundary violated: {violating}"


def test_tool_modules_do_not_depend_on_legacy_service_or_router_layer(project_root: Path) -> None:
    """Tools should not depend on legacy router/service layers."""
    tool_files = _python_files(project_root / "app" / "tools")
    forbidden = ("app.routers", "app.services", "fastapi")

    violating = []
    for file_path in tool_files:
        modules = _imported_modules(file_path)
        if _has_forbidden_import(modules, forbidden):
            violating.append(str(file_path.relative_to(project_root)))

    assert not violating, f"Tool import boundary violated: {violating}"
