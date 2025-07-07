# tests/notebooks/utils/test_evaluation.py

import pytest
from notebooks.utils.evaluation import PhenotypeEvaluator
from unittest.mock import Mock


@pytest.fixture
def mock_ground_truth_packet():
    mock_packet = Mock()
    mock_packet.list_phenotypes.return_value = ["Phen1", "Phen2"]
    return mock_packet


def test_perfect_prediction_counts(mock_ground_truth_packet):
    """
    Perfect prediction:
        predicted = ["Phen1","Phen2"]
        ground    = ["Phen1","Phen2"]

    ->  TP=2, FP=0, FN=0
    """
    evaluator = PhenotypeEvaluator()
    evaluator.check_phenotypes(["Phen1", "Phen2"], mock_ground_truth_packet)

    assert evaluator.true_positive == 2
    assert evaluator.false_positive == 0
    assert evaluator.false_negative == 0


def test_normalization_and_whitespace(mock_ground_truth_packet):
    """
    Whitespace and case should be ignored:
        predicted = [" PHEN1 ", "phen2"]
        ground    = ["Phen1","Phen2"]

    ->  still TP=2, FP=0, FN=0
    """
    evaluator = PhenotypeEvaluator()
    evaluator.check_phenotypes([" PHEN1 ", "phen2"], mock_ground_truth_packet)

    assert evaluator.true_positive == 2
    assert evaluator.false_positive == 0
    assert evaluator.false_negative == 0


def test_complex_example(mock_ground_truth_packet):
    """
    Ground truth    =  {A, B, C, E, X}
    Predicted       =  {A, B, D, F}

    - A, B -> TP (intersection size = 2)
    - D, F -> FP (each not in ground truth -> size = 2)
    - ground truth has 5 slots, but only 4 predictions -> FN=1
        (exactly one true label was never predicted)
    """
    mock_ground_truth_packet.list_phenotypes.return_value = ["A", "B", "C", "E", "X"]
    evaluator = PhenotypeEvaluator()
    evaluator.check_phenotypes(["A", "B", "D", "F"], mock_ground_truth_packet)

    assert evaluator.true_positive == 2
    assert evaluator.false_positive == 2
    assert evaluator.false_negative == 1


def test_single_truth_no_prediction(mock_ground_truth_packet):
    """
    Single-label ground truth with no predictions:
        - ground truth  =   ["Z"]
        - predicted     =   []

    Expect:
        - TP = 0    (no exact matches)
        - FP = 0    (no predictions at all)
        - FN = 1    (the one true label "Z" was never predicted)
    """
    # drive everything off the mock: single true label "Z", no predictions
    mock_ground_truth_packet.list_phenotypes.return_value = ["Z"]
    evaluator = PhenotypeEvaluator()
    # no predictions provided
    evaluator.check_phenotypes([], mock_ground_truth_packet)

    # verify that the lone true label counts as a false negative
    assert evaluator.true_positive == 0
    assert evaluator.false_positive == 0
    assert evaluator.false_negative == 1
