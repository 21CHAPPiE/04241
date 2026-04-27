"""Contract tests for dataset/path inputs and artifact-path outputs."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_module_from_file(module_name: str, module_file: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _required_positional_count(func: Any) -> int:
    signature = inspect.signature(func)
    return sum(
        1
        for parameter in signature.parameters.values()
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        and parameter.default is inspect.Parameter.empty
    )


def _path_from_result(result: Any) -> Path | None:
    if isinstance(result, tuple):
        for item in result:
            if isinstance(item, (str, Path)):
                candidate = Path(item)
                if candidate.exists():
                    return candidate
        return None
    if isinstance(result, Path):
        return result
    if isinstance(result, str):
        return Path(result)
    if isinstance(result, dict):
        for key in ("path", "artifact_path", "output_path", "file_path"):
            value = result.get(key)
            if isinstance(value, (str, Path)):
                return Path(value)
    return None


def test_resolve_dataset_path_accepts_path_input_and_returns_path(
    project_root: Path, dataset_file: Path
) -> None:
    """Dataset resolver should accept a path-like input and return a path-like output."""
    module_file = project_root / "app" / "core" / "io" / "paths.py"
    if not module_file.exists():
        pytest.skip("Pending parallel lane: app/core/io/paths.py")

    module = _load_module_from_file("mcp_paths_contract", module_file)
    resolver = getattr(module, "resolve_dataset_path", None)
    if not callable(resolver):
        pytest.skip("Pending parallel lane: resolve_dataset_path()")
    if _required_positional_count(resolver) > 1:
        pytest.skip("resolve_dataset_path() requires additional mandatory arguments")

    output = resolver(dataset_file)
    output_path = _path_from_result(output)
    assert output_path is not None, "resolve_dataset_path() must return a path-like value"
    assert output_path.exists(), "resolved dataset path must exist for existing input"


def test_create_run_directory_returns_existing_directory_path(
    project_root: Path, artifact_dir: Path
) -> None:
    """Run directory creator should return a path-like directory output."""
    module_file = project_root / "app" / "core" / "io" / "paths.py"
    if not module_file.exists():
        pytest.skip("Pending parallel lane: app/core/io/paths.py")

    module = _load_module_from_file("mcp_paths_contract", module_file)
    create_run_directory = getattr(module, "create_run_directory", None)
    if not callable(create_run_directory):
        pytest.skip("Pending parallel lane: create_run_directory()")
    if _required_positional_count(create_run_directory) > 2:
        pytest.skip("create_run_directory() requires additional mandatory arguments")

    output = create_run_directory("contract-test", run_root=artifact_dir)
    output_path = _path_from_result(output)
    assert output_path is not None, "create_run_directory() must return a path-like value"
    assert output_path.exists()
    assert output_path.is_dir()


def test_write_text_artifact_returns_written_artifact_path(
    project_root: Path, artifact_dir: Path
) -> None:
    """Text artifact writer should expose a path-like output that points to a created file."""
    module_file = project_root / "app" / "core" / "io" / "artifacts.py"
    if not module_file.exists():
        pytest.skip("Pending parallel lane: app/core/io/artifacts.py")

    module = _load_module_from_file("mcp_artifacts_contract", module_file)
    write_text_artifact = getattr(module, "write_text_artifact", None)
    if not callable(write_text_artifact):
        pytest.skip("Pending parallel lane: write_text_artifact()")

    required = _required_positional_count(write_text_artifact)
    if required > 3:
        pytest.skip("write_text_artifact() contract not yet stabilized")

    output = write_text_artifact(artifact_dir, "summary.txt", "ok")
    output_path = _path_from_result(output)
    assert output_path is not None, "write_text_artifact() must return a path-like value"
    assert output_path.exists()
    assert output_path.is_file()


def test_write_json_artifact_returns_written_artifact_path(
    project_root: Path, artifact_dir: Path
) -> None:
    """JSON artifact writer should expose a path-like output that points to a created file."""
    module_file = project_root / "app" / "core" / "io" / "artifacts.py"
    if not module_file.exists():
        pytest.skip("Pending parallel lane: app/core/io/artifacts.py")

    module = _load_module_from_file("mcp_artifacts_contract", module_file)
    write_json_artifact = getattr(module, "write_json_artifact", None)
    if not callable(write_json_artifact):
        pytest.skip("Pending parallel lane: write_json_artifact()")

    required = _required_positional_count(write_json_artifact)
    if required > 3:
        pytest.skip("write_json_artifact() contract not yet stabilized")

    output = write_json_artifact(artifact_dir, "summary.json", {"status": "ok"})
    output_path = _path_from_result(output)
    assert output_path is not None, "write_json_artifact() must return a path-like value"
    assert output_path.exists()
    assert output_path.is_file()
