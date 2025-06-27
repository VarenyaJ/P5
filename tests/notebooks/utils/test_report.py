import json
import pytest
from pathlib import Path
from sklearn.metrics import precision_score, recall_score, f1_score
from notebooks.utils.report import Report

def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        Report.create([0, 1], [0], "A", "E1", "M1")


def test_report_creation_and_metrics():
    y_true = [0, 1, 1, 0, 1]
    y_pred = [0, 1, 0, 0, 1]

    rpt = Report.create(y_true, y_pred, "tester", "exp1", "modelA", note="unit test")
    meta = rpt.metadata

    # Required metadata
    assert meta["creator"] == "tester"
    assert meta["experiment"] == "exp1"
    assert meta["model"] == "modelA"
    assert meta["num_samples"] == len(y_true)
    assert "date" in meta
    assert meta["note"] == "unit test"

    # Check metrics against sklearn
    exp_prec = precision_score(y_true, y_pred, average="macro", zero_division=0)
    exp_rec = recall_score(y_true, y_pred, average="macro", zero_division=0)
    exp_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    assert pytest.approx(exp_prec) == rpt.get_metric("precision")
    assert pytest.approx(exp_rec) == rpt.get_metric("recall")
    assert pytest.approx(exp_f1) == rpt.get_metric("f1_score")

    # Confusion matrix is square and correct size
    cm = rpt.confusion_matrix
    n_classes = len({*y_true, *y_pred})
    assert len(cm) == n_classes and all(len(row) == n_classes for row in cm)
