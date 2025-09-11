# tests/notebooks/utils/test_truth_alignment.py
"""
Unit tests for notebooks.utils.truth_alignment.

We create a tiny DataFrame + matching minimal phenopacket JSON files on disk,
then verify that:
- the aligner returns lists of equal length,
- subject IDs are discovered,
- wrapper exposes phenotypes (count-only sanity, not ontology).
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
   sys.path.insert(0, PROJECT_ROOT)

truth_mod = pytest.importorskip("notebooks.utils.truth_alignment")  # noqa: E402


def _write_minimal_pp(path: Path, patient_id: str, hpos=None):
   hpos = hpos or [{"type": {"id": "HP:0001250", "label": "Seizure"}}]
   data = {
       "id": patient_id,
       "subject": {"id": patient_id},
       "phenotypicFeatures": hpos,
       "metaData": {"created": "2020-01-01T00:00:00Z", "createdBy": "test", "phenopacketSchemaVersion": "2.0.2"},
   }
   path.write_text(json.dumps(data), encoding="utf-8")


def test_load_and_align_truth(tmp_path: Path):
   # Create minimal dataset DataFrame with two rows and real files on disk
   input_a = tmp_path / "a.txt"
   input_a.write_text("lorem", encoding="utf-8")
   input_b = tmp_path / "b.txt"
   input_b.write_text("ipsum", encoding="utf-8")
   truth_a = tmp_path / "a.json"
   _write_minimal_pp(truth_a, "patient-A")
   truth_b = tmp_path / "b.json"
   _write_minimal_pp(truth_b, "patient-B")

   df = pd.DataFrame(
       {"pmid": ["PMID_A", "PMID_B"], "input": [str(input_a), str(input_b)], "truth": [str(truth_a), str(truth_b)]}
   )

   alignment = truth_mod.load_and_align_truth(dataset_dataframe=df, maximum_rows=None)

   assert len(alignment.list_of_pmids_aligned) == 2
   assert len(alignment.list_of_input_paths_aligned) == 2
   assert len(alignment.list_of_truth_packets_wrapped) == 2
   assert not alignment.list_of_skipped_cases

   # Patient IDs surfaced
   assert alignment.list_of_patient_ids_from_truth == ["patient-A", "patient-B"]

   # Phenotype listing works on the wrapper
   first_pp = alignment.list_of_truth_packets_wrapped[0]
   phenos = first_pp.list_phenotypes()
   assert isinstance(phenos, list)
   assert len(phenos) >= 1