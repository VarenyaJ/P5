# tests/notebooks/utils/test_dataset_loading.py
"""
Unit tests for notebooks.utils.dataset_loading.

We create a temporary CSV with duplicate PMIDs and a mix of existing/missing
input paths and verify:
- required columns are validated,
- existence checks do not crash,
- deduplication keeps the first occurrence,
- returned stats are correct.
"""

import os
import sys
import csv
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
   sys.path.insert(0, PROJECT_ROOT)

from notebooks.utils.dataset_loading import (  # noqa: E402
   load_and_validate_dataset,
   REQUIRED_DATASET_COLUMNS,
)


def test_load_and_validate_dataset_happy_path(tmp_path: Path):
   # Create some dummy input/truth files
   existing_input = tmp_path / "paper1.txt"
   existing_input.write_text("hello world", encoding="utf-8")
   missing_input = tmp_path / "missing.txt"
   truth1 = tmp_path / "truth1.json"
   truth2 = tmp_path / "truth2.json"
   truth1.write_text("{}", encoding="utf-8")
   truth2.write_text("{}", encoding="utf-8")

   # Build a CSV with duplicates: pmid A appears twice; pmid B once
   csv_path = tmp_path / "dataset.csv"
   rows = [
       {"pmid": "PMID_A", "input": str(existing_input), "truth": str(truth1)},
       {"pmid": "PMID_A", "input": str(missing_input), "truth": str(truth1)},
       {"pmid": "PMID_B", "input": str(existing_input), "truth": str(truth2)},
   ]
   with csv_path.open("w", newline="", encoding="utf-8") as f:
       writer = csv.DictWriter(f, fieldnames=["pmid", "input", "truth"])
       writer.writeheader()
       writer.writerows(rows)

   df, stats = load_and_validate_dataset(
       dataset_csv_path=str(csv_path),
       max_input_existence_checks=3,
       verbose=False,  # avoid log noise in tests
   )

   # Required columns present
   assert set(df.columns) >= REQUIRED_DATASET_COLUMNS

   # Dedup keeps first row for PMID_A and the single row for PMID_B
   assert len(df) == 2
   assert df.iloc[0]["pmid"] == "PMID_A"
   assert df.iloc[1]["pmid"] == "PMID_B"

   # Stats sanity
   assert stats["rows_loaded"] == 3
   assert stats["duplicates_removed"] == 1
   assert stats["rows_after_dedup"] == 2


def test_load_and_validate_dataset_missing_csv_raises(tmp_path: Path):
   with pytest.raises(FileNotFoundError):
       load_and_validate_dataset(str(tmp_path / "nope.csv"))


def test_load_and_validate_dataset_missing_required_columns(tmp_path: Path):
   csv_path = tmp_path / "bad.csv"
   pd.DataFrame({"pmid": ["X"], "input": ["a.txt"]}).to_csv(csv_path, index=False)  # missing 'truth'
   with pytest.raises(KeyError):
       load_and_validate_dataset(str(csv_path))