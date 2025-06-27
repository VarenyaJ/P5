"""
report.py

Defines the Report dataclass for summarizing classification results, including confusion matrix, aggregate metrics, and experiment metadata.

Key imports:
- dataclass, field: auto-generate boilerplate (constructor, repr, etc.) and customize which fields are initialized by __init__.
- datetime: timestamp reports with the current date in ISO format.
- sklearn.metrics: compute confusion matrix, precision, recall, F1, and generate human-readable classification reports.
"""

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
    """
    Hold classification results, compute metrics, and persist to JSON.

    The @dataclass decorator:
    - Automatically creates __init__, __repr__, and __eq__ methods based on the declared fields.
    - Allows us to mark computed fields (confusion_matrix, metrics) with `field(init=False)`, so they are set in __post_init__ rather than passed by the caller.

    Parameters
    ----------
    y_true : List[Any]
        Ground-truth labels for each sample.
    y_pred : List[Any]
        Labels predicted by the model.
    metadata : Dict[str, Any]
        Experiment metadata. Required keys:
            - "date" : ISO date string (YYYY-MM-DD), generated via datetime.now()
            - "creator" : some individual/group/institution identifier
            - "experiment" : experiment name or ID
            - "model" : model name or version
        May include other entries (e.g. hyperparameters).


    Attributes
    ----------
    confusion_matrix : List[List[int]]
        Computed in __post_init__; rows=true labels, cols=predicted.
    metrics : Dict[str, float]
        Computed in __post_init__; keys "precision", "recall", "f1_score".
    """

    y_true: List[Any]
    y_pred: List[Any]
    metadata: Dict[str, Any]
    # These two fields are computed after __init__, not passed by the caller.
    confusion_matrix: List[List[int]] = field(init=False)
    metrics: Dict[str, float] = field(init=False)

    def __post_init__(self) -> None:
        """
        Called automatically after the dataclass-generated __init__.

        - Validates that y_true and y_pred have the same length.
        - Uses sklearn.metrics to compute confusion_matrix, precision, recall, and F1.
        - Logs each step via the module logger.

        Raises
        ------
        ValueError
            If lengths of y_true and y_pred differ.
        """
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
        """
        Construct a Report with automatic date stamping.

        - Uses datetime.now().date().isoformat() to generate metadata['date'].
        - Wraps all parameters into a metadata dict, adding 'num_samples'.

        Parameters
        ----------
        y_true : List[Any]
            Ground-truth labels.
        y_pred : List[Any]
            Predicted labels.
        creator : str
            Who ran the evaluation.
        experiment : str
            Experiment identifier.
        model : str
            Model name or version.
        **extra_metadata : Any
            Additional metadata entries (e.g. hyperparameters).


        Returns
        -------
        Report
            Ready-to-use report with metrics computed.

        Examples
        --------
        >>> rpt = Report.create([0,1,1], [0,0,1], creator="Alice", experiment="exp1", model="v1.0", notes="proof of concept")
        """
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
        """
        Write this Report out as a JSON file.

        Parameters
        ----------
        filepath : str
            Full path (including filename) to write JSON to.

        Raises
        ------
        IOError
            If writing to disk fails.
        """
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
        """
        Read a Report back from disk, re-computing metrics.

        Notes
        -----
        We call Report.create(...) so that any updates to metric logic
        are applied at load time (via __post_init__).

        Parameters
        ----------
        filepath : str
            Path to the JSON file previously written by save().

        Returns
        -------
        Report
            Fresh Report instance with metrics & confusion_matrix set.

        Raises
        ------
        FileNotFoundError
            If the given file does not exist.
        json.JSONDecodeError
            If the file is not valid JSON.
        """
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
        """
        Retrieve all computed macro-averaged metrics.

        Returns
        -------
        Dict[str, float]
            Keys: "precision", "recall", "f1_score".
        """
        logger.debug("get_metrics() called")
        return self.metrics

    def get_metric(self, metric: str) -> float:
        """
        Retrieve a single metric by name.

        Parameters
        ----------
        metric : str
            One of "precision", "recall", or "f1_score".

        Returns
        -------
        float
            The requested metric value.

        Raises
        ------
        KeyError
            If an unsupported metric key is requested.
        """
        logger.debug("get_metric('%s') called", metric)
        return self.metrics[metric]

    def __str__(self) -> str:
        """
        Render a human-readable classification report.

        Delegates to sklearn.metrics.classification_report:
        includes per-class precision/recall/F1 and support counts.

        Returns
        -------
        str
            Multi-line text table.
        """
        logger.debug("Generating classification_report string")
        return sk_classification_report(self.y_true, self.y_pred)
