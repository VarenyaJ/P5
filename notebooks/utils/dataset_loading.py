"""
notebooks/utils/dataset_loading.py

Loads and validates the phenopacket-store dataset CSV, performs light file
existence checks, and deduplicates rows by PMID.

Usage:
    from notebooks.utils.dataset_loading import load_and_validate_dataset

    dataframe_cases, dataset_stats = load_and_validate_dataset(
        dataset_csv_path=dataset_csv_path,
        max_input_existence_checks=10,
        verbose=True,
    )
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple
import pandas as pd
import logging

# Columns that must exist in the dataset CSV
REQUIRED_DATASET_COLUMNS = {"pmid", "input", "truth"}


def load_and_validate_dataset(
    dataset_csv_path: str, max_input_existence_checks: int = 10, verbose: bool = True
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Load and validate the dataset CSV that maps:
      - 'pmid'  → PubMed identifier
      - 'input' → path to the PDF (or .txt) used as LLM input
      - 'truth' → path to the corresponding ground-truth Phenopacket JSON

    Steps performed:
      1) Read the CSV from disk.
      2) Verify required columns exist.
      3) (Optional) Print existence checks for the first N 'input' file paths.
      4) Deduplicate rows by 'pmid' (keep first occurrence).
      5) Return the cleaned DataFrame and basic stats.

    Args:
        dataset_csv_path:
            Absolute path to the dataset CSV.
        max_input_existence_checks:
            How many rows (from the top) to check for file existence.
            Set to 0 to skip existence checks.
        verbose:
            If True, print progress, counts, and existence results.

    Returns:
        (dataframe_cases, dataset_stats)
            dataframe_cases : pd.DataFrame
            dataset_stats   : dict with keys:
                - 'rows_loaded'
                - 'duplicates_removed'
                - 'rows_after_dedup'
    """
    if not os.path.isfile(dataset_csv_path):
        raise FileNotFoundError(f"Dataset CSV not found: {dataset_csv_path}")

    # 1) Load the CSV
    dataframe_cases = pd.read_csv(dataset_csv_path)
    rows_loaded = len(dataframe_cases)
    if verbose:
        logger.info("[dataset] Loaded %d row(s) from CSV: %s", rows_loaded, dataset_csv_path)

    # 2) Verify required columns
    missing_columns = REQUIRED_DATASET_COLUMNS - set(dataframe_cases.columns)
    if missing_columns:
        raise KeyError(f"Dataset CSV missing required columns: {missing_columns}")

    # 3) Light existence checks (non-fatal; informational)
    if verbose and max_input_existence_checks > 0:
        logger.info("[dataset] Checking existence of first %d input files:", max_input_existence_checks)
        for file_path in dataframe_cases["input"].head(max_input_existence_checks):
            file_status = "FOUND" if os.path.isfile(file_path) else "MISSING"
            logger.info("  - %s: %s", file_path, file_status)

    # 4) Deduplicate by PMID (keep first)
    original_count = len(dataframe_cases)
    dataframe_cases = dataframe_cases.drop_duplicates(
        subset="pmid", keep="first"
    ).reset_index(drop=True)
    rows_after_dedup = len(dataframe_cases)
    duplicates_removed = original_count - rows_after_dedup

    if verbose:
        logger.info("[dataset] Deduplicated PMIDs: removed %d, now %d unique PMIDs", duplicates_removed, rows_after_dedup)

    dataset_stats = {
        "rows_loaded": rows_loaded,
        "duplicates_removed": duplicates_removed,
        "rows_after_dedup": rows_after_dedup,
    }
    return dataframe_cases, dataset_stats
