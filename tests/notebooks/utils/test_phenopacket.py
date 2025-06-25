# P5/tests/notebooks/utils/test_phenopacket.py

import json
import os
import tempfile

import pytest

from notebooks.utils.phenopacket import Phenopacket, InvalidPhenopacketError


@pytest.fixture
def sample_json() -> dict:  # CHANGED: renamed fixture & added return-type
   """
   Build a minimal but valid phenopacket JSON dict for testing.

   Returns
   -------
   dict
       A mapping with exactly three entries under "phenotypicFeatures":
       each entry has a "type" dict containing "id" and "label" keys.
   """
   return {
       "phenotypicFeatures": [
           {"type": {"id": "HP:0000001", "label": "Phenotype One"}},
           {"type": {"id": "HP:0000002", "label": "Phenotype Two"}},
           {"type": {"id": "HP:0000003", "label": "Phenotype Three"}},
       ]
   }


def test_count(sample_json):  # CHANGED: renamed from test_init_and_count & param name
   """
   Verify that initializing from a dict stores the JSON and
   that `count_phenotypes` returns the correct integer.
   Parameters
   ----------
   sample_json : dict
       Provided by fixture - contains three phenotypic features.
   """
   pp = Phenopacket(sample_json)
   # There are three features in our sample fixture
   assert pp.count_phenotypes == 3, "Less features than expected"
   # Always an int, never e.g. a float
   assert isinstance(pp.count_phenotypes, int)


def test_list_and_membership(sample_json):
   """
   Test the label-based API:
     - `list_phenotypes()` returns labels in insertion order.
     - `contains_phenotype(label)` matches only exact labels.
     - `contains_phenotype_id(id)` matches only exact HPO IDs.
   """
   pp = Phenopacket(sample_json)
   # Expect the labels exactly as listed in the fixture
   expected_labels = ["Phenotype One", "Phenotype Two", "Phenotype Three"]
   assert pp.list_phenotypes() == expected_labels

   # Label membership (positive/negative)
   assert pp.contains_phenotype("Phenotype Two") is True
   assert pp.contains_phenotype("Unknown Label") is False

   # ID membership (positive/negative)
   assert pp.contains_phenotype_id("HP:0000003") is True
   assert pp.contains_phenotype_id("HP:9999999") is False


def test_str_and_repr(sample_json):
   """
   Ensure that the string representations include the phenotype count:
     - repr(pp) should be unambiguous (for debugging).
     - str(pp) should be human-friendly.
   """
   pp = Phenopacket(sample_json)

   # __repr__ must exactly match our convention
   assert repr(pp) == "<Phenopacket phenotypes=3>"

   # __str__ must mention the count and pluralization correctly
   assert str(pp) == "Phenopacket with 3 phenotypic features"


def test_to_json_identity_and_mutation(sample_json):
   """
   The `to_json()` method should return the same underlying dict,
   not a deep copy. Mutating it updates the Phenopacket state.
   """
   pp = Phenopacket(sample_json)
   original = pp.to_json()

   # The returned object is identical (same memory address)
   # If we remove one feature, count_phenotypes reflects that
   # Ensures to_json() returns the same dict, so mutations update the instance
   assert original is sample_json
   original["phenotypicFeatures"].pop()
   assert pp.count_phenotypes == 2


def test_load_from_file_and_file_not_found(sample_json):
   """
   Validate the file-loading factory `load_from_file()`:
     1. Nonexistent path raises FileNotFoundError.
     2. A valid JSON on disk loads successfully.
   """
   # 1) Invalid path should error out
   with pytest.raises(FileNotFoundError):
       Phenopacket.load_from_file("does_not_exist.json")

   # 2) Write our fixture to a temp file and load it
   with tempfile.TemporaryDirectory() as tmpdir:
       filepath = os.path.join(tmpdir, "phenopacket.json")
       with open(filepath, "w", encoding="utf-8") as f:
           json.dump(sample_json, f)

       pp = Phenopacket.load_from_file(filepath)
       # Confirm it loaded exactly three features
       assert pp.count_phenotypes == 3
       assert pp.contains_phenotype("Phenotype Three")


@pytest.mark.parametrize(
   "bad_input",
   [
       [],  # not a dict
       "just a string",  # wrong top-level type
       123,  # wrong top-level type
       {"phenotypicFeatures": "not a list"},  # features must be a list
   ],
)
def test_invalid_structure_raises(bad_input):
   """
   The constructor should raise InvalidPhenopacketError if:
     - The top-level JSON isn't a dict.
     - "phenotypicFeatures" exists but is not a list.
   """
   # Each bad_input hits a different validation branch (root vs features-list)
   with pytest.raises(InvalidPhenopacketError):
       Phenopacket(bad_input)


def test_edge_case_empty_and_single_feature():
   """
   Boundary conditions:
     - Empty phenotypicFeatures -> count=0, no membership.
     - Single-entry -> count=1, membership works.
   """
   # Empty list case
   empty_pp = Phenopacket({"phenotypicFeatures": []})
   assert empty_pp.count_phenotypes == 0
   assert empty_pp.contains_phenotype("Anything") is False

   # Single-feature case
   single_pp = Phenopacket(
       {"phenotypicFeatures": [{"type": {"id": "HP:0000004", "label": "Solo"}}]}
   )
   assert single_pp.count_phenotypes == 1
   assert single_pp.list_phenotypes() == ["Solo"]
   assert single_pp.contains_phenotype("Solo") is True


def test_malformed_feature_entries_are_skipped(caplog):
   """
   If individual entries in `phenotypicFeatures` are malformed (e.g. missing
   'type' or non-dict 'type'), we should:
     - Not raise an exception.
     - Skip those entries with a logged warning.
     - Still correctly find valid entries.
   """
   caplog.set_level("WARNING")
   malformed = {
       "phenotypicFeatures": [
           {},  # no 'type' key
           {"type": "oops"},  # wrong type for 'type'
           {"type": {"id": "HP:0000005", "label": "Valid"}},  # the only good one
       ]
   }
   pp = Phenopacket(malformed)

   # Only one valid label should be listed
   assert pp.list_phenotypes() == ["Valid"]
   # contains_phenotype finds only the valid label
   assert pp.contains_phenotype("Valid") is True
   assert pp.contains_phenotype("Anything else") is False
   # Two warnings should have been emitted
   warnings = [r.message for r in caplog.records]
   assert any("malformed phenotypicFeature" in str(w) for w in warnings)
   #


#