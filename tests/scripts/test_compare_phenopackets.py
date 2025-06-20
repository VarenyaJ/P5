import pytest

from scripts.compare_phenopackets import compare_jsons


def test_perfect_match():
    # id & two tags ⇒ 3 leaves, all matched
    ref = {"id": 1, "tags": ["a", "b"]}
    out = {"id": 1, "tags": ["a", "b"]}
    assert compare_jsons(ref, out) == {"TP": 3, "FP": 0, "FN": 0}


def test_missing_and_hallucination():
    # id matches (TP=1); name missing (FN+1); foo extra (FP+1)
    ref = {"id": 1, "name": "Alice"}
    out = {"id": 1, "foo": "bar"}
    assert compare_jsons(ref, out) == {"TP": 1, "FP": 1, "FN": 1}


def test_type_mismatch_and_extra():
    # age wrong type → +1 FP & +1 FN; extra key → +1 FP
    ref = {"age": 5}
    out = {"age": "5", "extra": 0}
    assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 1}


def test_invalid_json_input():
    # Non‐dict/list → all 2 leaves counted as FN and FP
    ref = {"a": 1, "b": 2}
    out = "not a json"
    assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 2}


def test_nested_value_and_key():
    # Nested wrong height → +1 FP & +1 FN; extra weight → +1 FP
    # total_expected = 1 leaf under height
    ref = {"person": {"height": 170}}
    out = {"person": {"height": 160, "weight": 60}}
    # FN=1 (height wrong), FP=2 (height wrong + weight extra), TP=0
    assert compare_jsons(ref, out) == {"TP": 0, "FP": 2, "FN": 1}


def test_empty_dict_vs_list():
    # {} counts as 1 leaf; [] counts as 0 ⇒ mismatch ⇒ +1 FP & +1 FN
    ref = {"x": {}}
    out = {"x": []}
    assert compare_jsons(ref, out) == {"TP": 0, "FP": 1, "FN": 1}
