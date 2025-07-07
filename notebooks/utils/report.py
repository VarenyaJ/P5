# notebooks/utils/report.py

"""
report.py

- true_positive  (TP): a predicted label that exactly matches a label in the ground-truth set
- false_positive (FP): a predicted label that does not appear in the ground-truth set
- false_negative (FN): a ground-truth label that the model failed to predict
- true_negative  (TN): *labels not in ground-truth that the model also did not predict - this is always infinite in our open-world formulation, so in practice we set TN to 0 as a placeholder

Computes:
    - precision =   TP / (TP + FP)
    - recall    =   TP / (TP + FN)
    - f1_score  =   2.(precision.recall)/(precision+recall)
    - true/false-classification_report via `sklearn.metrics.classification_report()`, and a metadata dict containing:
        - creator
        - experiment
        - model
        - date
        - any extra keywords passed in.

Key methods:
    __init__            : Accepts raw counts + metadata, builds everything in memory.
    get_metrics         : Returns {"precision", "recall", "f1_score"}.
    get_metric          : Returns a single metric.
    __str__             : Renders the sklearn classification_report table.
    save                : Dumps all fields to a JSON file.
    @staticmethod load  : Reads that JSON back and reconstructs a Report.
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
        self.true_positive = true_positive
        self.false_positive = false_positive
        self.false_negative = false_negative
        self.true_negative = true_negative

        y_true, y_pred = self._build_vectors()

        # Force the class-order [1, 0]
        cm = sk_confusion_matrix(y_true, y_pred, labels=[1, 0])
        self.confusion_matrix: List[List[int]] = cm.tolist()
        #   [TP, FP], [FN, TN]]

        precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
        recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        self.metrics: Dict[str, float] = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }

        self.classification_report: str = sk_classification_report(
            y_true,
            y_pred,
            labels=[1, 0],
            target_names=["present", "absent"],
            zero_division=0,
        )
        self.metadata: Dict[str, Any] = {
            "creator": creator,
            "experiment": experiment,
            "model": model,
            "date": date.today().isoformat(),
            **metadata_extra,
        }

    def _build_vectors(self) -> tuple[list[int], list[int]]:
        """
        Internal helper: from the stored TP/FP/FN/TN counts, produce the y_true and y_pred lists in the correct order for sklearn metrics.
        """
        tp = self.true_positive
        fp = self.false_positive
        fn = self.false_negative
        tn = self.true_negative

        y_true = [1] * tp + [1] * fn + [0] * fp + [0] * tn
        y_pred = [1] * tp + [0] * fn + [1] * fp + [0] * tn

        return y_true, y_pred

    def get_metrics(self) -> Dict[str, float]:
        return self.metrics

    def get_metric(self, metric: str) -> float:
        """
        Raises KeyError if the key is invalid.
        """
        return self.metrics[metric]

    def __str__(self) -> str:
        """
        This is what `print(report)` will show.
        """
        return self.classification_report

    def save(self, filepath: str) -> None:
        """
        Persist this Report to disk as JSON.
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
        Load a JSON-dumped Report and reconstruct it. This will pull back the raw counts and metadata, then re-invoke the __init__ logic to recompute metrics and report.
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
