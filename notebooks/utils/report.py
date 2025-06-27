import json
import logging
from logging import NullHandler
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from sklearn.metrics import (
    confusion_matrix as sk_confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    classification_report as sk_classification_report,
)

# Module-level logger: silent by default unless the application configures logging.
logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())


@dataclass
class Report:
    y_true: List[Any]
    y_pred: List[Any]
    metadata: Dict[str, Any]
    # These two fields are computed after __init__, not passed by the caller.
    confusion_matrix: List[List[int]] = field(init=False)
    metrics: Dict[str, float] = field(init=False)

    def __post_init__(self) -> None:
        if len(self.y_true) != len(self.y_pred):
            logger.error(
                "Length mismatch: y_true has %d elements, y_pred has %d",
                len(self.y_true),
                len(self.y_pred),
            )
            raise ValueError("`y_true` and `y_pred` must be the same length")

        logger.debug("Computing confusion matrix for %d samples", len(self.y_true))
        cm = sk_confusion_matrix(self.y_true, self.y_pred)
        self.confusion_matrix = cm.tolist()
        logger.info("Confusion matrix computed: %s", self.confusion_matrix)

        prec = precision_score(
            self.y_true, self.y_pred, average="macro", zero_division=0
        )
        rec = recall_score(self.y_true, self.y_pred, average="macro", zero_division=0)
        f1 = f1_score(self.y_true, self.y_pred, average="macro", zero_division=0)
        self.metrics = {"precision": prec, "recall": rec, "f1_score": f1}
        (
            logger.info(
                "Metrics computed -- precision: %.4f, recall: %.4f, f1_score: %.4f",
                prec,
                rec,
                f1,
            )
        )

    @classmethod
    def create(
        cls,
        y_true: List[Any],
        y_pred: List[Any],
        creator: str,
        experiment: str,
        model: str,
        **extra_metadata: Any
    ) -> "Report":
        meta: Dict[str, Any] = {
            "date": datetime.now().date().isoformat(),
            "creator": creator,
            "experiment": experiment,
            "model": model,
            "num_samples": len(y_true),
        }
        meta.update(extra_metadata)
        logger.debug("Creating report with metadata: %s", meta)
        return cls(y_true=y_true, y_pred=y_pred, metadata=meta)

    def save(self, filepath: str) -> None:
        payload = {
            "y_true": self.y_true,
            "y_pred": self.y_pred,
            "metadata": self.metadata,
            "confusion_matrix": self.confusion_matrix,
            "metrics": self.metrics,
        }
        logger.debug("Saving report to %s", filepath)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        logger.info("Report saved successfully")

    @staticmethod
    def load(filepath: str) -> "Report":
        logger.debug("Loading report from %s", filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Pull out core metadata needed by create()
        core_keys = ("creator", "experiment", "model", "num_samples")
        core = {k: data["metadata"][k] for k in core_keys}
        extra = {
            k: v for k, v in data["metadata"].items() if k not in (*core_keys, "date")
        }
        rpt = Report.create(
            y_true=data["y_true"],
            y_pred=data["y_pred"],
            creator=core["creator"],
            experiment=core["experiment"],
            model=core["model"],
            **extra,
        )
        logger.info("Report loaded and metrics re-computed")
        return rpt

    def get_metrics(self) -> Dict[str, float]:
        logger.debug("get_metrics() called")
        return self.metrics

    def get_metric(self, metric: str) -> float:
        logger.debug("get_metric('%s') called", metric)
        return self.metrics[metric]