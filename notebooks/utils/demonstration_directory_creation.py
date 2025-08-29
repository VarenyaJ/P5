#!/usr/bin/env python3
"""
demonstration_directory_creation.py

Purpose:
- Centralize project directory setup for the demonstration notebook.
- Patch PYTHONPATH with source and utilities directories.
- Verify imports work for core project utilities (phenopacket, report, evaluation).
- Create all standard folders and files used by the demonstration.

Usage (in a notebook or script):
    from utils.demonstration_directory_creation import (
        patch_pythonpath_and_create_demonstration_directories,
        DemonstrationPaths
    )

    paths = patch_pythonpath_and_create_demonstration_directories(emit_verbose_logs=True)

    # Access key paths via the returned dataclass:
    print(paths.dataset_csv_file_path)
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging


# ----------------------------
# Dataclass: store all important paths
# ----------------------------

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemonstrationPaths:
    project_root_directory: Path
    source_code_directory: Path
    notebooks_utilities_directory: Path

    pdf_input_directory: Path
    ground_truth_notebooks_directory: Path
    dataset_csv_file_path: Path

    experimental_data_root_directory: Path
    llm_raw_output_directory: Path
    validated_jsons_output_directory: Path
    evaluation_report_file_path: Path


# ----------------------------
# Internal helpers
# ----------------------------


def _ensure_directory_on_sys_path(directory: Path) -> None:
    """Add directory to sys.path if it exists and is not already present."""
    if not directory.is_dir():
        raise FileNotFoundError(f"Expected folder on PYTHONPATH: {directory}")
    resolved_path = str(directory.resolve())
    if resolved_path not in sys.path:
        sys.path.insert(0, resolved_path)


def _infer_project_root(explicit_root: Optional[Path] = None) -> Path:
    """Infer project root (default: parent of CWD)."""
    if explicit_root is not None:
        return explicit_root.resolve()
    return (Path.cwd() / "..").resolve()


def build_demonstration_paths(project_root_directory: Path) -> DemonstrationPaths:
    """Build all key paths needed for the demonstration pipeline."""
    source_code_directory = project_root_directory / "src"
    notebooks_utilities_directory = project_root_directory / "notebooks" / "utils"

    pdf_input_directory = (
        source_code_directory
        / "P5"
        / "scripts"
        / "data"
        / "tmp"
        / "phenopacket_store"
        / "pmid_pdfs"
    )
    ground_truth_notebooks_directory = (
        source_code_directory
        / "P5"
        / "scripts"
        / "data"
        / "tmp"
        / "phenopacket_store"
        / "notebooks"
    )
    dataset_csv_file_path = (
        source_code_directory
        / "P5"
        / "scripts"
        / "data"
        / "tmp"
        / "PMID_PDF_Phenopacket_list_in_phenopacket_store.csv"
    )

    experimental_data_root_directory = project_root_directory / "experimental-data"
    llm_raw_output_directory = experimental_data_root_directory / "llm_output_dir"
    validated_jsons_output_directory = (
        experimental_data_root_directory / "validated_jsons"
    )
    evaluation_report_file_path = (
        project_root_directory / "reports" / "first_report.json"
    )

    return DemonstrationPaths(
        project_root_directory=project_root_directory,
        source_code_directory=source_code_directory,
        notebooks_utilities_directory=notebooks_utilities_directory,
        pdf_input_directory=pdf_input_directory,
        ground_truth_notebooks_directory=ground_truth_notebooks_directory,
        dataset_csv_file_path=dataset_csv_file_path,
        experimental_data_root_directory=experimental_data_root_directory,
        llm_raw_output_directory=llm_raw_output_directory,
        validated_jsons_output_directory=validated_jsons_output_directory,
        evaluation_report_file_path=evaluation_report_file_path,
    )


# ----------------------------
# Public entrypoint
# ----------------------------


def patch_pythonpath_and_create_demonstration_directories(
    project_root_override: Optional[str | Path] = None, emit_verbose_logs: bool = False
) -> DemonstrationPaths:
    """
    Patch sys.path and ensure demonstration directories exist.

    Args:
        project_root_override: manually specify project root (else use parent of CWD).
        emit_verbose_logs: if True, print paths and folder creation logs.

    Returns:
        DemonstrationPaths dataclass with all resolved paths.
    """
    # 1) Resolve project root and build all paths
    project_root_directory = _infer_project_root(
        Path(project_root_override) if project_root_override else None
    )
    paths = build_demonstration_paths(project_root_directory)

    # 2) Ensure sys.path contains src/ and notebooks/utils/
    _ensure_directory_on_sys_path(paths.source_code_directory)
    _ensure_directory_on_sys_path(paths.notebooks_utilities_directory)

    if emit_verbose_logs:
        logger.info(
            "PYTHONPATH patched with: %s %s",
            str(paths.source_code_directory),
            str(paths.notebooks_utilities_directory),
        )
        logger.info("Project Root:         %s", paths.project_root_directory)
        logger.info("Source Folder:        %s", paths.source_code_directory)
        logger.info("Utilities Folder:     %s", paths.notebooks_utilities_directory)

    # 3) Validate utils can be imported (early failure if environment is wrong)
    try:
        from phenopacket import Phenopacket, InvalidPhenopacketError  # noqa
        from report import Report  # noqa
        from evaluation import PhenotypeEvaluator  # noqa
    except ImportError as import_error:
        raise ImportError(
            f"Could not import project utils after patching PYTHONPATH: {import_error}"
        ) from import_error

    # 4) Ensure directories exist
    for directory in [
        paths.pdf_input_directory,
        paths.ground_truth_notebooks_directory,
        paths.dataset_csv_file_path.parent,
        paths.llm_raw_output_directory,
        paths.validated_jsons_output_directory,
        paths.evaluation_report_file_path.parent,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    if emit_verbose_logs:
        logger.info(
            "Created/checked PDF input folder:                  %s",
            paths.pdf_input_directory,
        )
        logger.info(
            "Created/checked ground-truth notebooks folder:     %s",
            paths.ground_truth_notebooks_directory,
        )
        logger.info(
            "Created/checked dataset CSV parent folder:         %s",
            paths.dataset_csv_file_path.parent,
        )
        logger.info(
            "Created/checked experimental data root:            %s",
            paths.experimental_data_root_directory,
        )
        logger.info(
            "Created/checked LLM raw outputs folder:            %s",
            paths.llm_raw_output_directory,
        )
        logger.info(
            "Created/checked validated JSONs folder:            %s",
            paths.validated_jsons_output_directory,
        )
        logger.info(
            "Created/checked reports folder:                    %s",
            paths.evaluation_report_file_path.parent,
        )

    return paths


if __name__ == "__main__":
    # When run as a script, do the setup and print a succinct summary.
    resolved_paths = patch_pythonpath_and_create_demonstration_directories(
        emit_verbose_logs=True
    )
    logger.info("Environment setup complete.")
    logger.info("Dataset CSV path:   %s", resolved_paths.dataset_csv_file_path)
    logger.info("Report output path: %s", resolved_paths.evaluation_report_file_path)
    logger.info("=== Final Path Summary ===")
    logger.info(
        "Created the PDF inputs folder:                               %s",
        resolved_paths.pdf_input_directory,
    )
    logger.info(
        "Created the ground truth folder:                             %s",
        resolved_paths.ground_truth_notebooks_directory,
    )
    logger.info(
        "Created the PATH for the CSV of `phenopacket-store`:         %s",
        resolved_paths.dataset_csv_file_path,
    )
    logger.info(
        "Created the PATH for the experimentally generated files:     %s",
        resolved_paths.experimental_data_root_directory,
    )
    logger.info(
        "Created the LLM outputs folder:                              %s",
        resolved_paths.llm_raw_output_directory,
    )
    logger.info(
        "Created the validated JSONs folder:                          %s",
        resolved_paths.validated_jsons_output_directory,
    )
    logger.info(
        "Created the evaluation report path:                          %s",
        resolved_paths.evaluation_report_file_path,
    )
