# tests/notebooks/utils/test_hpo_extraction.py
"""
Unit tests for notebooks.utils.hpo_extraction.

We stub the model-calling function to avoid any runtime dependency on Ollama.
The tests focus on:
- Parsing paths (sentinel block, scavenger, results[], single object)
- Strict validation (regex, evidence substring)
- Phenopacket construction helper
"""

import os
import sys
from typing import Tuple, List, Dict

import pytest

# Ensure project root is on sys.path (repo_root/notebooks/utils/...)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
   sys.path.insert(0, PROJECT_ROOT)

from notebooks.utils import hpo_extraction as hpo  # noqa: E402


@pytest.fixture()
def clinical_text() -> str:
   # Keep small to avoid chunking and to keep deterministic behavior.
   # Include tokens that can be used as evidence.
   return (
       "The patient had drug-resistant infantile epilepsy and repeated seizures. "
       "Exam also noted hypotonia."
   )


def _set_stub_model(monkeypatch, payload: str):
   """Replace _ask_model with a stub returning `payload` for every call."""
   def _fake_ask(*_args, **_kwargs) -> str:
       return payload
   monkeypatch.setattr(hpo, "_ask_model", _fake_ask)


def test_extract_with_sentinel_block(monkeypatch, clinical_text):
   """Happy path: model returns a properly wrapped array between <<<JSON / JSON>>>."""
   payload = (
       "prefix\n"
       "<<<JSON\n"
       '[{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"seizures"}]\n'
       "JSON>>>\n"
       "suffix\n"
   )
   _set_stub_model(monkeypatch, payload)
   items, raw = hpo.extract_hpo_terms(clinical_text, return_raw_model_text=True)
   assert raw is not None
   assert items == [{"hpo_id": "HP:0001250", "hpo_label": "Seizure"}]


def test_extract_with_results_array_fallback(monkeypatch, clinical_text):
   """Model nests the array under a 'results' key."""
   payload = '{"results":[{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"seizures"}]}'
   _set_stub_model(monkeypatch, payload)
   items, _ = hpo.extract_hpo_terms(clinical_text)
   assert items == [{"hpo_id": "HP:0001250", "hpo_label": "Seizure"}]


def test_extract_with_array_scavenger_fallback(monkeypatch, clinical_text):
   """Model returns a naked array without sentinels; the scavenger regex should find it."""
   payload = '[{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"seizures"}]'
   _set_stub_model(monkeypatch, payload)
   items, _ = hpo.extract_hpo_terms(clinical_text)
   assert items == [{"hpo_id": "HP:0001250", "hpo_label": "Seizure"}]


def test_extract_with_single_object_fallback(monkeypatch, clinical_text):
   """Model returns a single object; validator should accept exactly one."""
   payload = '{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"seizures"}'
   _set_stub_model(monkeypatch, payload)
   items, _ = hpo.extract_hpo_terms(clinical_text)
   assert items == [{"hpo_id": "HP:0001250", "hpo_label": "Seizure"}]


def test_extract_retry_path(monkeypatch, clinical_text):
   """
   First call returns garbage (no valid items), retry returns a valid sentinel block.
   The implementation retries once on the first chunk.
   """
   calls = {"n": 0}

   def _fake_ask(_model: str, _prompt: str, **_kwargs) -> str:
       calls["n"] += 1
       if calls["n"] == 1:
           return "{}"  # invalid -> trigger retry
       return (
           "<<<JSON\n"
           '[{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"seizures"}]\n'
           "JSON>>>"
       )

   monkeypatch.setattr(hpo, "_ask_model", _fake_ask)
   items, _ = hpo.extract_hpo_terms(clinical_text, return_raw_model_text=True)
   assert calls["n"] >= 2  # retried
   assert items == [{"hpo_id": "HP:0001250", "hpo_label": "Seizure"}]


def test_extract_filters_invalid_ids(monkeypatch, clinical_text):
   """Invalid HPO ID format or missing evidence must be rejected by validator."""
   bad_id = (
       "<<<JSON\n"
       '[{"hpo_id":"HP:1250","hpo_label":"Seizure","evidence":"seizures"}]\n'
       "JSON>>>"
   )
   _set_stub_model(monkeypatch, bad_id)
   items, _ = hpo.extract_hpo_terms(clinical_text)
   assert items == []

   missing_evidence = (
       "<<<JSON\n"
       '[{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":""}]\n'
       "JSON>>>"
   )
   _set_stub_model(monkeypatch, missing_evidence)
   items, _ = hpo.extract_hpo_terms(clinical_text)
   assert items == []


def test_build_minimal_phenopacket_from_hpo_list():
   """Ensure helper builds a minimal, schema-like dict with validated items only."""
   # one valid + one invalid
   hpo_list: List[Dict[str, str]] = [
       {"hpo_id": "HP:0001250", "hpo_label": "Seizure"},
       {"hpo_id": "HP:1250", "hpo_label": "x"},  # invalid id -> dropped
   ]
   packet = hpo.build_minimal_phenopacket_from_hpo_list("patient-1", hpo_list)
   assert packet["id"] == "patient-1"
   assert packet["subject"]["id"] == "patient-1"
   assert "metaData" in packet
   assert packet["phenotypicFeatures"] == [
       {"type": {"id": "HP:0001250", "label": "Seizure"}}
   ]