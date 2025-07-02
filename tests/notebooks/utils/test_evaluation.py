import json
import pytest

from notebooks.utils.evaluation import PhenotypeEvaluator
from notebooks.utils.phenopacket import Phenopacket


@pytest.fixture
def path_to_true_phenopacket(tmp_path):
    """
    Create a minimal ground truth Phenopacket JSON file with two HPO labels:
      - "Phen1"
      - "Phen2"
    Returns the file path to this JSON.
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
    Perfect prediction (Predicted == Ground Truth):
      - true_positive  == 2
      - false_positive == 0
      - false_negative == 0

    Expected confusion_matrix == [[2, 0], [0, 0]]
    """
    evaluator = PhenotypeEvaluator()
    ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

    predicted_labels = ["Phen1", "Phen2"]
    evaluator.check_phenotypes(predicted_labels, ground_truth_packet)
    report = evaluator.report(creator="alice", experiment="exp1", model="modelA")

    assert report.metadata["true_positive"] == 2
    assert report.metadata["false_positive"] == 0
    assert report.metadata["false_negative"] == 0
    assert report.confusion_matrix == [[2, 0], [0, 0]]


def test_perfect_prediction_metrics_and_report_text(path_to_true_phenopacket):
    """
    Perfect prediction yields:
      precision == 1.0
      recall    == 1.0
      f1_score  == 1.0

    classification_report text must include 'present' and 'absent'.
    """
    evaluator = PhenotypeEvaluator()
    ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

    evaluator.check_phenotypes(["Phen1", "Phen2"], ground_truth_packet)
    report = evaluator.report("alice", "exp1", "modelA")

    metrics = report.metrics
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["f1_score"] == pytest.approx(1.0)

    report_text = report.classification_report.lower()
    assert "present" in report_text
    assert "absent" in report_text


def test_false_positive_and_miss_counts_and_metrics(path_to_true_phenopacket):
    """
    Predict one correct label and one hallucinated label:
      - true_positive  == 1
      - false_positive == 1
      - false_negative == 1

    Expected confusion_matrix == [[1, 1], [1, 0]]
    Metrics: precision=0.5, recall=0.5, f1_score=0.5
    """
    evaluator = PhenotypeEvaluator()
    ground_truth_packet = Phenopacket.load_from_file(path_to_true_phenopacket)

    evaluator.check_phenotypes(["Phen1", "Fake"], ground_truth_packet)
    report = evaluator.report("bob", "exp2", "modelB")

    assert report.metadata["true_positive"] == 1
    assert report.metadata["false_positive"] == 1
    assert report.metadata["false_negative"] == 1
    assert report.confusion_matrix == [[1, 1], [1, 0]]

    metrics = report.metrics
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["f1_score"] == pytest.approx(0.5)


def test_multiple_batches_accumulation(path_to_true_phenopacket, tmp_path):
    """
    Two-sample accumulation:
    1) Sample #1: predict ["Phen1"] vs ground truth ["Phen1","Phen2"]
       -> TP=1, FP=0, FN=1
    2) Sample #2: predict ["Phen1","Extra"] vs ground truth ["Phen1"]
       -> TP+=1, FP+=1, FN+=0
    Cumulative:
      true_positive  == 2
      false_positive == 1
      false_negative == 1
    Confusion matrix == [[2, 1], [1, 0]]
    Metrics == precision=2/3, recall=2/3, f1_score=2/3
    """
    evaluator = PhenotypeEvaluator()

    # First sample
    gt_packet1 = Phenopacket.load_from_file(path_to_true_phenopacket)
    evaluator.check_phenotypes(["Phen1"], gt_packet1)

    # Second sample
    data2 = {"phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "Phen1"}}]}
    packet2_file = tmp_path / "true_packet2.json"
    packet2_file.write_text(json.dumps(data2), encoding="utf-8")
    gt_packet2 = Phenopacket.load_from_file(str(packet2_file))
    evaluator.check_phenotypes(["Phen1", "Extra"], gt_packet2)

    report = evaluator.report("carol", "exp3", "modelC")

    assert report.metadata["true_positive"] == 2
    assert report.metadata["false_positive"] == 1
    assert report.metadata["false_negative"] == 1
    assert report.confusion_matrix == [[2, 1], [1, 0]]

    metrics = report.metrics
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["f1_score"] == pytest.approx(2 / 3)
