# tests/notebooks/utils/test_phenopacket_store_dataset_setup.py
"""
Lightweight test for notebooks.utils.phenopacket_store_dataset_setup.

We mock subprocess.run so no external commands are executed. The goal is to
exercise control flow and ensure a plausible pmids.pkl path is returned.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
   sys.path.insert(0, PROJECT_ROOT)

setup_mod = pytest.importorskip("notebooks.utils.phenopacket_store_dataset_setup")  # noqa: E402


def test_setup_dataset_returns_pmids_path(tmp_path, monkeypatch):
   # Arrange dummy folders
   src_folder = str(tmp_path / "src")
   pdf_dir = str(tmp_path / "pdfs")
   gt_dir = str(tmp_path / "truth_notebooks")
   dataset_csv = str(tmp_path / "dataset.csv")
   Path(src_folder).mkdir(parents=True, exist_ok=True)
   Path(pdf_dir).mkdir(parents=True, exist_ok=True)
   Path(gt_dir).mkdir(parents=True, exist_ok=True)

   # Mock subprocess.run to no-op
   class _Completed:
       def __init__(self): self.returncode = 0
   monkeypatch.setattr(setup_mod.subprocess, "run", lambda *a, **k: _Completed())

   # Act
   pmids_pkl = setup_mod.setup_phenopacket_store_dataset(
       src_folder=src_folder,
       pdf_input_directory=pdf_dir,
       ground_truth_notebooks_directory=gt_dir,
       dataset_csv_path=dataset_csv,
       max_pdfs_to_download=0,
   )

   # Assert: function returns some path ending with pmids.pkl
   assert isinstance(pmids_pkl, str)
   assert pmids_pkl.endswith("pmids.pkl")
