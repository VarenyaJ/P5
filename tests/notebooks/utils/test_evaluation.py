# tests/notebooks/utils/test_evaluation.py

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
    Return the path to that file.
    """
    data = {
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000001", "label": "Phen1"}},
            {"type": {"id": "HP:0000002", "label": "Phen2"}},
        ]
    }
    p = tmp_path / "true_packet.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_perfect_prediction_counts(path_to_true_phenopacket):
    """
    Perfect prediction:
      predicted = ["Phen1","Phen2"]
      ground    = ["Phen1","Phen2"]

    -> TP=2, FP=0, FN=0
    """
    evaluator = PhenotypeEvaluator()
    gt = Phenopacket.load_from_file(path_to_true_phenopacket)

    evaluator.check_phenotypes(["Phen1", "Phen2"], gt)

    assert evaluator.true_positive == 2
    assert evaluator.false_positive == 0
    assert evaluator.false_negative == 0


def test_normalization_and_whitespace(path_to_true_phenopacket):
    """
    Whitespace and case should be ignored:
      predicted = [" PHEN1 ", "phen2"]
      ground    = ["Phen1","Phen2"]

    -> still TP=2, FP=0, FN=0
    """
    evaluator = PhenotypeEvaluator()
    gt = Phenopacket.load_from_file(path_to_true_phenopacket)

    evaluator.check_phenotypes([" PHEN1 ", "phen2"], gt)

    assert evaluator.true_positive == 2
    assert evaluator.false_positive == 0
    assert evaluator.false_negative == 0


def test_complex_example(tmp_path):
    """
    Ground truth = {A, B, C, E, X}
    Predicted    = {A, B, D, F}

    - A, B -> TP (intersection size = 2)
    - D, F -> FP (each not in ground truth -> size = 2)
    - ground truth has 5 slots, but only 4 predictions -> FN=1
      (exactly one true label was never predicted)
    """
    labels_gt = ["A", "B", "C", "E", "X"]
    data = {
        "phenotypicFeatures": [
            {"type": {"id": f"HP:{i:07d}", "label": lbl}}
            for i, lbl in enumerate(labels_gt, start=1)
        ]
    }
    p = tmp_path / "example.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    gt = Phenopacket.load_from_file(str(p))

    evaluator = PhenotypeEvaluator()
    evaluator.check_phenotypes(["A", "B", "D", "F"], gt)

    assert evaluator.true_positive == 2
    assert evaluator.false_positive == 2
    assert evaluator.false_negative == 1


def test_single_truth_no_prediction(tmp_path):
    """
    Single-label ground truth with no predictions:
        - ground truth = ["Z"]
        - predicted    = []

    Expect:
        - TP = 0  (no exact matches)
        - FP = 0  (no predictions at all)
        - FN = 1  (the one true label "Z" was never predicted)
    """
    # build a Phenopacket JSON containing exactly one label "Z"
    data = {"phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "Z"}}]}
    p = tmp_path / "single_truth.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    gt = Phenopacket.load_from_file(str(p))

    evaluator = PhenotypeEvaluator()
    # no predictions provided
    evaluator.check_phenotypes([], gt)

    # verify that the lone true label counts as a false negative
    assert evaluator.true_positive == 0
    assert evaluator.false_positive == 0
    assert evaluator.false_negative == 1
