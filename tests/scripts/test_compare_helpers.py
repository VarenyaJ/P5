import pytest
from scripts.compare_phenopackets import (
   _count_leaf_fields,
   _count_extra_keys,
   _tally_diff_fp_fn,
   compute_prf,
)
from jsoncomparison import Compare, NO_DIFF


def test_count_leaf_fields_edge_cases():
   # Scalars => 1; {} => 1; [] => 0; nested => sum of leaves
   assert _count_leaf_fields(42) == 1
   assert _count_leaf_fields({}) == 1
   assert _count_leaf_fields([]) == 0
   assert _count_leaf_fields({"a": 1, "b": [2, 3], "c": {}}) == 4


def test_count_extra_keys_various():
   # One extra at top level
   assert _count_extra_keys({"x": 1}, {"x": 1, "y": 2}) == 1
   # Nested extra & top-level extra
   ref = {"a": {"b": 1}}
   cand = {"a": {"b": 1, "c": 2}, "d": 3}
   assert _count_extra_keys(ref, cand) == 2
   # List-of-dicts case
   ref = [{"k": 1}, {"m": 2}]
   cand = [{"k": 1}, {"m": 2, "n": 3}]
   assert _count_extra_keys(ref, cand) == 1


def test_tally_diff_fp_fn_length_and_value():
   # Perfect match
   assert _tally_diff_fp_fn(NO_DIFF) == (0, 0)
   # Missing y, wrong x => FP=1 (missing y?), FN=2 (wrong x + missing y)
   true = {"x": 1, "y": 2}
   cand = {"x": 99}
   diff = Compare().check(true, cand)
   assert _tally_diff_fp_fn(diff) == (1, 2)


def test_tally_diff_list_length_mismatch():
   # Candidate shorter by 1 => FN = 1
   diff = Compare().check([1, 2, 3], [1, 2])
   assert _tally_diff_fp_fn(diff) == (0, 1)
   # Candidate longer by 2 => FP = 2
   diff = Compare().check([1, 2], [1, 2, 3, 4])
   assert _tally_diff_fp_fn(diff) == (2, 0)


def test_compute_prf_basic():
   metrics = {"TP": 3, "FP": 1, "FN": 2}
   prf = compute_prf(metrics)
   assert pytest.approx(prf["precision"], 1e-9) == 3 / 4
   assert pytest.approx(prf["recall"],    1e-9) == 3 / 5
   assert pytest.approx(prf["f1"],        1e-9) == 2 * (3/4)*(3/5) / ((3/4)+(3/5))