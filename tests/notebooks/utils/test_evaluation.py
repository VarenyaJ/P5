"""
tests/notebooks/utils/test_evaluation.py
"""

"""
Unit tests for PhenotypeEvaluator and Report classes.

These tests verify:
1) Basic TP/FP/FN counting (perfect match).
2) Label normalization (case and whitespace handling).
3) Synonym mapping behavior.
4) Zero-division configuration for metrics.
5) A complex example illustrating set-difference logic for TP/FP/FN.

Each test builds a minimal ground truth phenopacket JSON file via the `path_to_true_phenopacket` fixture or inline data,
then uses `PhenotypeEvaluator` to accumulate counts, produces a `Report`, and asserts on its metadata,
confusion_matrix, and metrics.
"""

import json
import pytest
from pathlib import Path

from notebooks.utils.evaluation import PhenotypeEvaluator, Report
from notebooks.utils.phenopacket import Phenopacket


@pytest.fixture
def path_to_true_phenopacket(tmp_path):
   """
   Fixture: Create a minimal ground-truth Phenopacket JSON file with two HPO labels:
   - "Phen1"
   - "Phen2"
   This JSON exercises basic loading and list_phenotypes() behavior. Returns the file path to the written JSON.
   """
   data = {
   "phenotypicFeatures": [
       {"type": {"id": "HP:0000001", "label": "Phen1"}},
       {"type": {"id": "HP:0000002", "label": "Phen2"}},
       ]
   }
   true_file = tmp_path / "true_packet.json"
   true_file.write_text(json.dumps(data), encoding="utf-8")
   return str(true_file)


def test_perfect_prediction_counts(path_to_true_phenopacket):
   """
   Test: Perfect prediction scenario.

   Input:
       predicted_labels = ["Phen1", "Phen2"]
       ground_truth_packet contains exactly those two labels.

   Expected:
       - true_positive  == 2 (both labels matched)
       - false_positive == 0 (no extra labels predicted)
       - false_negative == 0 (no true labels missed)
       - confusion_matrix == [[2, 0], [0, 0]]
   """
   evaluator = PhenotypeEvaluator()
   ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

   evaluator.check_phenotypes(["Phen1", "Phen2"], ground_truth_packet)
   report = evaluator.report("alice", "exp1", "modelA")

   # Assertions verify metadata counts and matrix layout
   assert report.metadata["true_positive"] == 2
   assert report.metadata["false_positive"] == 0
   assert report.metadata["false_negative"] == 0
   assert report.confusion_matrix == [[2, 0], [0, 0]]


def test_normalization_and_whitespace(path_to_true_phenopacket):
   """
   Test: Label normalization handles case-insensitivity and whitespace.

   Input:
       predicted_labels = [" PHEN1 ", "phen2"]
       ground_truth labels are ["Phen1","Phen2"].

   Reasoning:
       - Leading/trailing spaces should be stripped.
       - Case differences should be normalized to lowercase for matching.

   Expected all matches -> TP=2, FP=0, FN=0
   """
   evaluator = PhenotypeEvaluator()
   ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

   evaluator.check_phenotypes([" PHEN1 ", "phen2"], ground_truth_packet)
   report = evaluator.report("bob", "exp2", "modelB")

   assert report.metadata["true_positive"] == 2
   assert report.metadata["false_positive"] == 0
   assert report.metadata["false_negative"] == 0


def test_synonym_mapping(path_to_true_phenopacket):
   """
   Test: Synonym mapping transforms nonstandard labels to canonical ones.

   Setup a synonym_map: map "short stature" -> "phen1".
   Input predicted_labels = ["Phen2", " short STATURE "]
       - "Phen2" matches directly.
       - " short STATURE " is normalized and mapped to "phen1".
   Ground truth: ["Phen1","Phen2"].

   Expected:
       - After mapping, predicted set = {"phen1","phen2"} -> perfect match.
       - TP=2, FP=0, FN=0.
   """
   synonym_map = {"short stature": "phen1"}
   evaluator = PhenotypeEvaluator(synonym_map=synonym_map)
   ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

   evaluator.check_phenotypes(["Phen2", " short STATURE "], ground_truth_packet)
   report = evaluator.report("carol", "exp3", "modelC")

   assert report.metadata["true_positive"] == 2
   assert report.metadata["false_positive"] == 0
   assert report.metadata["false_negative"] == 0


def test_zero_division_behavior(path_to_true_phenopacket):
   """
   Test: Metrics when no predictions are made (predicted_labels=[]).

   Input:
       predicted_labels = []
       ground_truth = ["Phen1","Phen2"] -> FN=2, TP=0, FP=0.

   Default zero_division (0.0):
       - precision undefined -> 0.0
       - recall    undefined -> 0.0
       - f1_score  undefined -> 0.0

   Override zero_division=None:
       - metrics become None for precision, recall, f1_score.
   """
   evaluator = PhenotypeEvaluator()
   ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

   evaluator.check_phenotypes([], ground_truth_packet)
   report_default = evaluator.report("dave", "exp4", "modelD")
   assert report_default.metrics["precision"] == 0.0
   assert report_default.metrics["recall"]    == 0.0
   assert report_default.metrics["f1_score"]  == 0.0

   report_none = evaluator.report("dave", "exp4", "modelD", zero_division=None)
   assert report_none.metrics["precision"] is None
   assert report_none.metrics["recall"]    is None
   assert report_none.metrics["f1_score"]  is None


def test_complex_example(tmp_path):
   """
   Test: Complex scenario illustrating set-difference logic.

   Ground truth labels = {A,B,C,E,X}
   Predicted labels    = {A,B,D,F}

   Computation:
       TP = |GT ? PRED| = 2
       FP = |PRED - GT| = 2
       FN = |GT - PRED| = 3

   Metrics:
       precision = 2/(2+2) = 0.5
       recall    = 2/(2+3)= 0.4
       f1_score  ? 0.4444
   """
   labels_gt = ["A", "B", "C", "E", "X"]
   data = {
       "phenotypicFeatures": [
           {"type": {"id": f"HP:{i:07d}", "label": lbl}}
           for i, lbl in enumerate(labels_gt, start=1)
       ]
   }
   fp = tmp_path / "example.json"
   fp.write_text(json.dumps(data), encoding="utf-8")
   ground_truth_packet = Phenopacket.load_from_file(str(fp))

   evaluator = PhenotypeEvaluator()
   evaluator.check_phenotypes(["A", "B", "D", "F"], ground_truth_packet)
   report = evaluator.report("tester", "expX", "modelY")

   # Verify counts
   assert report.metadata["true_positive"]  == 2
   assert report.metadata["false_positive"] == 2
   assert report.metadata["false_negative"] == 3

   # Verify metrics
   m = report.metrics
   assert m["precision"] == pytest.approx(0.5)
   assert m["recall"]    == pytest.approx(2/5)
   assert m["f1_score"]  == pytest.approx(2 * 0.5 * (2/5) / (0.5 + 2/5))