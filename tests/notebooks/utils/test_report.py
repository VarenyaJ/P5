# tests/notebooks/utils/test_report.py

import json
import pytest

from notebooks.utils.report import Report
from sklearn.metrics import precision_score, recall_score, f1_score


@pytest.fixture
def sample_counts():
    """
    Provide a canonical set of counts to test against:
      TP=2, FP=1, FN=1, TN=0
    Then:
      y_true  = [1,1,0,1]  # TP×2, TN×0, FN×1, FP×1
      y_pred  = [1,1,1,0]  # TP×2, TN×0, FN×0, FP×1
    """
    return dict(
        true_positive=2,
        false_positive=1,
        false_negative=1,
        true_negative=0,
    )


def test_report_initialization_and_confusion_matrix(sample_counts):
    """
    Given the sample_counts fixture, verify:
      - metadata fields exist and include a date
      - confusion_matrix == [[2,1],[1,0]]
    """
    rpt = Report(
        **sample_counts,
        creator="tester",
        experiment="exp1",
        model="modelA",
        notes="unit test"
    )

    # Metadata
    meta = rpt.metadata
    assert meta["creator"] == "tester"
    assert meta["experiment"] == "exp1"
    assert meta["model"] == "modelA"
    assert "date" in meta
    assert meta["notes"] == "unit test"

    # Confusion matrix layout: [[TP,FP],[FN,TN]]
    assert rpt.confusion_matrix == [[2, 1], [1, 0]]


def test_metrics_match_sklearn_macro(sample_counts):
    """
    Confirm that Report.metrics align with sklearn.metrics.macro-average
    on the implicit y_true/y_pred constructed from sample_counts.
    """
    rpt = Report(**sample_counts, creator="tester", experiment="exp1", model="modelA")
    # reconstruct y_true/y_pred exactly as Report does
    y_true = (
        [1] * sample_counts["true_positive"]
        + [0] * sample_counts["true_negative"]
        + [1] * sample_counts["false_negative"]
        + [0] * sample_counts["false_positive"]
    )
    y_pred = (
        [1] * sample_counts["true_positive"]
        + [0] * sample_counts["true_negative"]
        + [0] * sample_counts["false_negative"]
        + [1] * sample_counts["false_positive"]
    )

    exp_prec = precision_score(y_true, y_pred, average="macro", zero_division=0)
    exp_rec = recall_score(y_true, y_pred, average="macro", zero_division=0)
    exp_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    assert pytest.approx(exp_prec) == rpt.get_metric("precision")
    assert pytest.approx(exp_rec) == rpt.get_metric("recall")
    assert pytest.approx(exp_f1) == rpt.get_metric("f1_score")


def test_str_includes_headers(sample_counts):
    """
    __str__ should emit a table that mentions 'precision', 'recall', 'f1-score'.
    """
    rpt = Report(**sample_counts, creator="u", experiment="e", model="m")
    s = str(rpt).lower()
    assert "precision" in s
    assert "recall" in s
    assert "f1-score" in s


def test_save_and_load(tmp_path, sample_counts):
    """
    Saving to disk and loading back should preserve:
      - counts
      - metadata fields
      - confusion_matrix
      - metrics
    """
    rpt = Report(**sample_counts, creator="tester", experiment="exp2", model="modelB")
    out = tmp_path / "report.json"
    rpt.save(str(out))

    # JSON must contain our top‐level keys
    data = json.loads(out.read_text(encoding="utf-8"))
    for key in (
        "true_positive",
        "false_positive",
        "false_negative",
        "true_negative",
        "metadata",
        "confusion_matrix",
        "metrics",
        "classification_report",
    ):
        assert key in data

    # load and re‐compare
    rpt2 = Report.load(str(out))
    # counts → reflected in confusion_matrix
    assert rpt2.confusion_matrix == rpt.confusion_matrix
    # metrics identical
    assert rpt2.metrics == rpt.metrics
    # metadata fields preserved
    for fld in ("creator", "experiment", "model"):
        assert rpt2.metadata[fld] == rpt.metadata[fld]
