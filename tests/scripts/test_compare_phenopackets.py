"""
Unit tests for compare_phenopackets.compare_jsons

To run these tests:
   pytest tests/scripts/test_compare_phenopackets.py -v
"""

import os
import sys

# Add the scripts/ folder to sys.path so we can import compare_phenopackets.py directly
scripts_dir = os.path.abspath(
   os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "scripts")
)
sys.path.insert(0, scripts_dir)

from compare_phenopackets import compare_jsons

def test_perfect_match():
   """All fields match exactly: TP = total, FP = 0, FN = 0."""
   ref = {"id": 1, "name": "Alice", "tags": ["a", "b"]}
   out = {"id": 1, "name": "Alice", "tags": ["a", "b"]}
   assert compare_jsons(ref, out) == {"TP": 4, "FP": 0, "FN": 0}

def test_missing_field():
   """Missing the 'name' field: TP=1 (id), FN=1, FP=0."""
   ref = {"id": 1, "name": "Alice"}
   out = {"id": 1}
   assert compare_jsons(ref, out) == {"TP": 1, "FP": 0, "FN": 1}

def test_wrong_value_and_extra():
   """
   - 'id' wrong -> FN+1, FP+1
   - extra 'foo' -> FP+1
   => TP=0, FP=2, FN=1
   """
   ref = {"id": 1}
   out = {"id": 2, "foo": 123}
   assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 1}

def test_non_json_output():
   """Non-dict/list output -> all fields missed & hallucinated."""
   ref = {"id": 1, "name": "Alice"}
   out = "not json"
   # total_expected = 2 -> FP=2, FN=2, TP=0
   assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 2}

def test_extra_nested_dict_key():
   """
   Nested dict has one matching leaf and one extra key:
   - 'name' matches -> TP
   - extra 'foo' -> FP
   => TP=1, FP=1, FN=0
   """
   ref = {"person": {"name": "Alice"}}
   out = {"person": {"name": "Alice", "foo": 123}}
   assert compare_jsons(ref, out) == {"TP": 1, "FP": 1, "FN": 0}