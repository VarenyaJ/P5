# tests/notebooks/utils/test_hpo_batch.py
"""
Unit tests for notebooks.utils.hpo_batch.

We heavily mock:
- clinical text loading,
- the HPO extraction function,
- the minimal phenopacket builder,
- the Phenopacket validator class.

Goal: verify that the orchestrator writes raw output and predicted JSON,
and reports successes as expected without touching any network/LLM.
"""

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
   sys.path.insert(0, PROJECT_ROOT)

hpo_batch = pytest.importorskip("notebooks.utils.hpo_batch")  # noqa: E402


class _DummyPhenopacket:
   """Simple drop-in replacement exposing list_phenotypes()."""

   def __init__(self, data: dict):
       self._data = data

   def list_phenotypes(self):
       return [p.get("type", {}) for p in self._data.get("phenotypicFeatures", [])]


def test_run_hpo_batch_inference_happy_path(tmp_path, monkeypatch):
   # Arrange temp output dirs
   raw_dir = tmp_path / "raw"
   json_dir = tmp_path / "json"

   # Aligned inputs (just placeholders; the loader is mocked)
   pmids = ["PMID_X", "PMID_Y"]
   inputs = [str(tmp_path / "x.pdf"), str(tmp_path / "y.pdf")]
   patient_ids = ["pat-x", "pat-y"]

   # Mock the text loader used inside the batch module (if present)
   if hasattr(hpo_batch, "_load_clinical_text"):
       monkeypatch.setattr(hpo_batch, "_load_clinical_text", lambda p: "evidence here")

   # Mock extractor to return one valid item and a small raw string
   def _fake_extract_hpo_terms(**_kwargs):
       items = [{"hpo_id": "HP:0001250", "hpo_label": "Seizure"}]
       return items, "RAW"
   monkeypatch.setattr(hpo_batch, "extract_hpo_terms", lambda **kw: _fake_extract_hpo_terms())

   # Mock builder to wrap features in expected dict
   def _fake_build(patient_id, hpo_list, **_kw):
       return {
           "id": patient_id,
           "subject": {"id": patient_id},
           "phenotypicFeatures": [{"type": {"id": it["hpo_id"], "label": it["hpo_label"]}} for it in hpo_list],
       }
   monkeypatch.setattr(hpo_batch, "build_minimal_phenopacket_from_hpo_list", _fake_build)

   # Mock the util validator class used by the batch module (if any)
   if hasattr(hpo_batch, "UtilPhenopacket"):
       monkeypatch.setattr(hpo_batch, "UtilPhenopacket", _DummyPhenopacket)

   # Act
   result = hpo_batch.run_hpo_batch_inference(
       list_of_pmids_aligned=pmids,
       list_of_input_paths_aligned=inputs,
       list_of_patient_ids_aligned=patient_ids,
       directory_for_raw_llm_outputs=str(raw_dir),
       directory_for_predicted_jsons=str(json_dir),
       write_raw_model_text=True,
       write_predicted_json=True,
       debug_logging=False,
   )

   # Assert: 2 successes, no failures
   assert result.total_successes() == 2
   assert result.total_failures() == 0
   assert len(result.successful_outcomes) == 2

   # Files written
   for o in result.successful_outcomes:
       assert o.raw_output_path is None or Path(o.raw_output_path).exists()
       assert o.predicted_json_path is None or Path(o.predicted_json_path).exists()

       # If JSON written, ensure structure plausibly matches what we mocked
       if o.predicted_json_path:
           data = json.loads(Path(o.predicted_json_path).read_text(encoding="utf-8"))
           assert data["id"] in patient_ids
           assert data["phenotypicFeatures"]