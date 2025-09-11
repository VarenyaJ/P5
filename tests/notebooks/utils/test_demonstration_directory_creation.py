# tests/notebooks/utils/test_demonstration_directory_creation.py
"""
Smoke test for notebooks.utils.demonstration_directory_creation.

We exercise the helper in an isolated temp "repo root" by:
- creating a minimal repo-like skeleton (src/ and notebooks/utils/),
- writing tiny stub modules (phenopacket, report, evaluation) so the helper's
  import checks succeed,
- calling the helper with project_root_override to avoid touching the real repo,
- asserting key output directories exist.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make the project importable so we can import the util module itself.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

demo = pytest.importorskip("notebooks.utils.demonstration_directory_creation")  # noqa: E402


def _write_stub_modules(utils_dir: Path) -> None:
    """Create minimal stubs the util tries to import."""
    (utils_dir / "phenopacket.py").write_text(
        "class InvalidPhenopacketError(Exception):\n"
        "    pass\n"
        "class Phenopacket:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (utils_dir / "report.py").write_text(
        "class Report:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (utils_dir / "evaluation.py").write_text(
        "class PhenotypeEvaluator:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        pass\n",
        encoding="utf-8",
    )


def test_patch_pythonpath_and_create_demonstration_directories(tmp_path, monkeypatch):
    # Create an isolated "repo root" under the tmp dir.
    fake_root = tmp_path / "repo_root"
    utils_dir = fake_root / "notebooks" / "utils"
    (fake_root / "src").mkdir(parents=True, exist_ok=True)
    utils_dir.mkdir(parents=True, exist_ok=True)

    # Provide stub modules so the util's import checks pass.
    _write_stub_modules(utils_dir)

    # Work from some child of the fake repo (not required, but realistic).
    monkeypatch.chdir(fake_root / "notebooks")

    # Call the helper, explicitly overriding the project root so we don't touch the real repo.
    paths = demo.patch_pythonpath_and_create_demonstration_directories(
        project_root_override=fake_root,
        emit_verbose_logs=False,
    )

    # Sanity checks: the helper should have produced/verified these locations.
    assert Path(paths.source_code_directory).is_dir()
    assert Path(paths.notebooks_utilities_directory).is_dir()
    assert Path(paths.pdf_input_directory).is_dir()
    assert Path(paths.ground_truth_notebooks_directory).is_dir()
    assert Path(paths.experimental_data_root_directory).is_dir()
    assert Path(paths.llm_raw_output_directory).is_dir()
    assert Path(paths.validated_jsons_output_directory).is_dir()
    assert Path(paths.evaluation_report_file_path).parent.is_dir()

    # Optional: confirm that our stubs are importable via the patched PYTHONPATH.
    import importlib

    phenopacket = importlib.import_module("phenopacket")
    report = importlib.import_module("report")
    evaluation = importlib.import_module("evaluation")

    assert hasattr(phenopacket, "Phenopacket")
    assert hasattr(phenopacket, "InvalidPhenopacketError")
    assert hasattr(report, "Report")
    assert hasattr(evaluation, "PhenotypeEvaluator")
