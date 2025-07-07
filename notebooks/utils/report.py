# notebooks/utils/report.py

"""
report.py

Defines the Report class for summarizing extraction performance in terms of
true positives, false positives, false negatives, and true negatives.

Eventually, Report will capture all four slots of the confusion matrix:

       - true_positive  (TP): a predicted label that exactly matches a label in the ground-truth set
       - false_positive (FP): a predicted label that does *not* appear in the ground-truth set
       - false_negative (FN): a ground-truth label that the model failed to predict
       - true_negative  (TN): *labels not in ground-truth that the model also did not predict* -- this is always infinite in our open-world formulation, so in practice we set TN to 0 as a placeholder

   And it will also compute:
       - precision  = TP / (TP + FP)
       - recall     = TP / (TP + FN)
       - f1_score   = 2.(precision.recall)/(precision+recall)

   Plus a true/false-classification_report via `sklearn.metrics.classification_report()`, and a metadata dict containing:
       - creator
       - experiment
       - model
       - date
       - any extra keywords passed in.

Responsibilities:
   - Build internal y_true/y_pred lists from raw TP/FP/FN/TN counts.
   - Compute a 2x2 confusion matrix, macro-averaged precision, recall, F1, and a scikit-learn text classification_report.
   - Hold experiment metadata (creator, experiment, model, date, plus any extras).
   - Persist itself to JSON (save) and restore from JSON (load), round-tripping all counts, metrics, and the classification_report string.

Key methods:
 __init__      : Accepts raw counts + metadata, builds everything in memory.
 get_metrics   : Returns {"precision", "recall", "f1_score"}.
 get_metric    : Returns a single metric.
 __str__       : Renders the sklearn classification_report table.
 save          : Dumps all fields to a JSON file.
 @staticmethod load : Reads that JSON back and reconstructs a Report.
"""

import json
import logging
from logging import NullHandler
from datetime import date
from typing import Any, Dict, List

from sklearn.metrics import (
    confusion_matrix as sk_confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    classification_report as sk_classification_report,
)

# Silence logger unless the application configures it
logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())


class Report:
    def __init__(
        self,
        true_positive: int,
        false_positive: int,
        false_negative: int,
        true_negative: int,
        creator: str,
        experiment: str,
        model: str,
        **metadata_extra: Any
    ) -> None:
        """
        Parameters
        ----------
        true_positive : int
            Number of exact matches (predicted ? truth).
        false_positive : int
            Number of predictions not in the ground truth.
        false_negative : int
            Number of ground-truth labels never predicted.
        true_negative : int
            Number of "negatives" correctly not predicted.  (Usually zero in open-ended label space.)
        creator : str
            Identifier of who ran the evaluation.
        experiment : str
            Experiment name or ID.
        model : str
            Model name or version.
        **metadata_extra : Any
            Any additional metadata (e.g. hyperparameters).
        """
        # 1) Store raw counts
        self.true_positive = true_positive
        self.false_positive = false_positive
        self.false_negative = false_negative
        self.true_negative = true_negative

        # 2) Build y_true/y_pred for sklearn
        #    Order is important: we must mirror the way confusion_matrix()
        #    and metrics expect them:
        #      1) TP samples -> y_true=1, y_pred=1
        #      2) FN samples -> y_true=1, y_pred=0
        #      3) FP samples -> y_true=0, y_pred=1
        #      4) TN samples -> y_true=0, y_pred=0
        y_true: List[int] = (
            [1] * true_positive
            + [1] * false_negative
            + [0] * false_positive
            + [0] * true_negative
        )
        y_pred: List[int] = (
            [1] * true_positive
            + [0] * false_negative
            + [1] * false_positive
            + [0] * true_negative
        )

        # 3) Compute confusion matrix, forcing the class-order [1, 0]
        cm = sk_confusion_matrix(y_true, y_pred, labels=[1, 0])
        self.confusion_matrix: List[List[int]] = cm.tolist()
        #             [[TP, FP],
        #              [FN, TN]]

        # 4) Compute macro-averaged metrics
        precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
        recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        self.metrics: Dict[str, float] = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }

        # 5) Generate the human-readable classification report
        #    with labels "present" (1) and "absent" (0)
        self.classification_report: str = sk_classification_report(
            y_true,
            y_pred,
            labels=[1, 0],
            target_names=["present", "absent"],
            zero_division=0,
        )

        # 6) Assemble metadata (always include date + passed fields)
        self.metadata: Dict[str, Any] = {
            "creator": creator,
            "experiment": experiment,
            "model": model,
            "date": date.today().isoformat(),
            **metadata_extra,
        }

    def get_metrics(self) -> Dict[str, float]:
        """Return the computed precision, recall, and f1_score."""
        return self.metrics

    def get_metric(self, metric: str) -> float:
        """
        Return one of 'precision', 'recall' or 'f1_score'.
        Raises KeyError if the key is invalid.
        """
        return self.metrics[metric]

    def __str__(self) -> str:
        """
        Render the sklearn classification_report.
        This is what `print(report)` will show.
        """
        return self.classification_report

    def save(self, filepath: str) -> None:
        """
        Persist this Report to disk as JSON.

        The JSON top-level keys will include:
          - true_positive, false_positive, false_negative, true_negative
          - metadata
          - confusion_matrix
          - metrics
          - classification_report
        """
        payload = {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "true_negative": self.true_negative,
            "metadata": self.metadata,
            "confusion_matrix": self.confusion_matrix,
            "metrics": self.metrics,
            "classification_report": self.classification_report,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

    @staticmethod
    def load(filepath: str) -> "Report":
        """
        Load a JSON-dumped Report and reconstruct it.

        This will pull back the raw counts and metadata, then re-invoke the __init__ logic to recompute metrics and report.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        rpt = Report(
            true_positive=data["true_positive"],
            false_positive=data["false_positive"],
            false_negative=data["false_negative"],
            true_negative=data["true_negative"],
            creator=data["metadata"]["creator"],
            experiment=data["metadata"]["experiment"],
            model=data["metadata"]["model"],
            # round-trip any extra metadata
            **{
                k: v
                for k, v in data["metadata"].items()
                if k not in ("creator", "experiment", "model", "date")
            },
        )
        return rpt


