import pytest
from scripts.compare_phenopackets import compare_jsons


def test_perfect_match():
   ref = {"id": 1, "tags": ["a", "b"]}
   out = {"id": 1, "tags": ["a", "b"]}
   assert compare_jsons(ref, out) == {"TP": 3, "FP": 0, "FN": 0}


def test_missing_and_hallucination():
   ref = {"id": 1, "name": "Alice"}
   out = {"id": 1, "foo": "bar"}
   assert compare_jsons(ref, out) == {"TP": 1, "FP": 1, "FN": 1}


def test_type_mismatch_and_extra():
   ref = {"age": 5}
   out = {"age": "5", "extra": 0}
   assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 1}


def test_invalid_json_input():
   ref = {"a": 1, "b": 2}
   out = "not a json"
   assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 2}


def test_nested_value_and_key():
   ref = {"person": {"height": 170}}
   out = {"person": {"height": 160, "weight": 60}}
   assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 1}


def test_empty_dict_vs_list():
   ref = {"x": {}}
   out = {"x": []}
   # Type mismatch {} vs [] -> FP+1,FN+1
   assert compare_jsons(ref, out) == {"TP": 0, "FP": 1, "FN": 1}