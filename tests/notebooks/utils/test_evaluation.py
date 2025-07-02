"""
tests/notebooks/utils/test_evaluation.py

Unit tests for PhenotypeEvaluator and Report classes.

These tests verify:
1) Basic TP/FP/FN counting (perfect match).
2) Label normalization (case and whitespace handling).
3) Synonym mapping behavior.
4) Zero-division configuration for metrics.
5) A complex example illustrating set-difference logic for TP/FP/FN.
"""

import json
import pytest

from notebooks.utils.evaluation import PhenotypeEvaluator
from notebooks.utils.phenopacket import Phenopacket


@pytest.fixture
def path_to_true_phenopacket(tmp_path):
    """
    Create a minimal ground-truth Phenopacket JSON file with two HPO labels:
      - "Phen1"
      - "Phen2"
    Return the file path.
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
    Perfect prediction:
      TP=2, FP=0, FN=0
    Confusion matrix == [[2, 0], [0, 0]]
    """
    evaluator = PhenotypeEvaluator()
    ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

    evaluator.check_phenotypes(["Phen1", "Phen2"], ground_truth_packet)
    report = evaluator.report("alice", "exp1", "modelA")

    assert report.metadata["true_positive"] == 2
    assert report.metadata["false_positive"] == 0
    assert report.metadata["false_negative"] == 0
    assert report.confusion_matrix == [[2, 0], [0, 0]]


def test_normalization_and_whitespace(path_to_true_phenopacket):
    """
    Ensure normalization strips extra spaces and ignores case:
      [" PHEN1 ", "phen2"] should count as perfect match.
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
    Provide a synonym_map so that predicted 'short stature' maps to 'phen1':
      ground truth contains 'Phen1'; we map ' short STATURE ' -> 'phen1'.
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
    When no predictions are made (predicted_labels=[]),
    precision & recall denominators = 0 -> both metrics should equal default zero_division.
    """
    evaluator = PhenotypeEvaluator()
    ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

    evaluator.check_phenotypes([], ground_truth_packet)  # TP=0, FP=0, FN=2
    report_default = evaluator.report("dave", "exp4", "modelD")
    assert report_default.metrics["precision"] == 0.0
    assert report_default.metrics["recall"] == 0.0
    assert report_default.metrics["f1_score"] == 0.0

    report_none = evaluator.report("dave", "exp4", "modelD", zero_division=None)
    assert report_none.metrics["precision"] is None
    assert report_none.metrics["recall"] is None
    assert report_none.metrics["f1_score"] is None


def test_complex_example(tmp_path):
    """
    GT labels = A,B,C,E,X
    PRED labels = A,B,D,F

    -> TP = 2 (A,B)
    -> FP = 2 (D,F)
    -> FN = 3 (C,E,X)
    precision = 2/4 = 0.5
    recall    = 2/5 = 0.4
    f1_score  = 2.(0.5.0.4)/(0.5+0.4) ? 0.4444
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

    # counts
    assert report.metadata["true_positive"] == 2
    assert report.metadata["false_positive"] == 2
    assert report.metadata["false_negative"] == 3

    # metrics
    m = report.metrics
    assert m["precision"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(2 / 5)
    assert m["f1_score"] == pytest.approx(2 * 0.5 * (2 / 5) / (0.5 + 2 / 5))
