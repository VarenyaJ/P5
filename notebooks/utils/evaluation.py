"""
evaluation.py

Stateful evaluator for LLM-extracted HPO labels.

Provides:
- Report: holds confusion matrix, metrics, classification report, and metadata.
- PhenotypeEvaluator: collects true_positive, false_positive, false_negative counts
by comparing predicted labels to a ground truth Phenopacket.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import date

from notebooks.utils.phenopacket import Phenopacket
from sklearn.metrics import classification_report

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Report:
    def __init__(self, **kwargs)
        # Intentionally empty, removing all stuf functionality and saving for the report-class

    def __init__(
        self,
        creator: str,
        experiment: str,
        model: str,
        true_positive: int,
        false_positive: int,
        false_negative: int,
        zero_division: Optional[float] = 0.0,
        **metadata_extra: Any
    ) -> None:
        """
        Initialize a Report with counts, metrics, classification report, and metadata.

        Parameters
        ----------
        creator : str
            Who ran the evaluation.
        experiment : str
            Experiment ID or name.
        model : str
            Model name or version.
        true_positive : int
            Number of correctly predicted labels.
        false_positive : int
            Number of labels predicted but not present in ground truth.
        false_negative : int
            Number of ground truth labels not predicted.
        zero_division : float or None
            Value to assign to precision, recall, or f1 when their denominator is zero.
            If None, metrics will be set to None in undefined cases.
        metadata_extra : Any
            Additional metadata entries (e.g., hyperparameters).
        """

        # 1) Assemble metadata dict
        self.metadata: Dict[str, Any] = {
            "creator": creator,
            "experiment": experiment,
            "model": model,
            "date": date.today().isoformat(),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        }
        self.metadata.update(metadata_extra)

        # 2) Build confusion matrix
        self.confusion_matrix: List[List[int]] = [
            [true_positive, false_positive],
            [false_negative, 0],
        ]

        # 3) Compute macro metrics
        if (true_positive + false_positive) > 0:
            precision = true_positive / (true_positive + false_positive)
        else:
            precision = zero_division

        # 3b) Compute recall, honoring zero_division=None if requested
        if zero_division is None:
            recall = None
        elif (true_positive + false_negative) > 0:
            recall = true_positive / (true_positive + false_negative)
        else:
            recall = zero_division

        # 3c) Compute F1 score
        if precision is None or recall is None or (precision + recall) == 0:
            f1_score = zero_division
        else:
            f1_score = 2 * precision * recall / (precision + recall)

        self.metrics = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
        }

        # 4) Generate synthetic labels for classification_report
        #    For each true positive: (1,1)
        #    For each false negative: (1,0)
        #    For each false positive: (0,1)
        y_true: List[int] = (
            [1] * true_positive + [1] * false_negative + [0] * false_positive
        )
        y_pred: List[int] = (
            [1] * true_positive + [0] * false_negative + [1] * false_positive
        )

        self.classification_report: str = classification_report(
            y_true,
            y_pred,
            labels=[1, 0],
            target_names=["present", "absent"],
            zero_division=0,
        )


class PhenotypeEvaluator:
    """
    Accumulates HPO-extraction evaluation counts across multiple samples.

    Methods
    -------
    check_phenotypes(predicted_labels, ground_truth_packet)
        Updates internal counts of true_positive, false_positive, false_negative.
    report(creator, experiment, model, **metadata_extra) -> Report
        Constructs and returns a Report summarizing all counts.
    """

    def __init__(self, synonym_map: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize counters and optional synonym map.

        Parameters
        ----------
        synonym_map : dict, optional
            Mapping from synonym strings (already lowercase/stripped) to
            canonical label strings to apply before counting.
        """
        self._true_positive: int = 0
        self._false_positive: int = 0
        self._false_negative: int = 0
        self._synonym_map = synonym_map or {}

    @property
    def true_positive(self) -> int:
        """Total true positives accumulated so far."""
        return self._true_positive

    @property
    def false_positive(self) -> int:
        """Total false positives accumulated so far."""
        return self._false_positive

    @property
    def false_negative(self) -> int:
        """Total false negatives accumulated so far."""
        return self._false_negative

    def check_phenotypes(
        self, hpo_labels: List[str], ground_truth_packet: Phenopacket
    ) -> None:
        """
        Compare a single sample's predicted HPO labels against the ground truth and update counts.

        Steps
        -----
        1) Normalize each label (strip whitespace, lowercase).
        2) Map synonyms if present.
        3) Build sets:
             true_hpo_term_set         = set(processed ground truth labels)
             experimental_hpo_term_set = set(processed predicted labels)
        4) Count via set differences:
             true_positive  = |true && pred|
             false_positive = |pred - true|
             false_negative = |true - pred|
        5) Accumulate counts internally.
        """

        def _normalize_and_map(label: str) -> str:
            norm = label.strip().lower()
            return self._synonym_map.get(norm, norm)

        true_hpo_term_set = {
            _normalize_and_map(label) for label in ground_truth_packet.list_phenotypes()
        }
        experimental_hpo_term_set = {_normalize_and_map(label) for label in hpo_labels}

        true_positive = len(true_hpo_term_set & experimental_hpo_term_set)
        false_positive = len(experimental_hpo_term_set - true_hpo_term_set)
        false_negative = len(true_hpo_term_set - experimental_hpo_term_set)

        logger.debug(
            "Sample evaluation: TP=%d, FP=%d, FN=%d",
            true_positive,
            false_positive,
            false_negative,
        )

        self._true_positive += true_positive
        self._false_positive += false_positive
        self._false_negative += false_negative

    def report(
        self,
        creator: str,
        experiment: str,
        model: str,
        zero_division: Optional[float] = 0.0,
        **metadata_extra: Any
    ) -> Report:
        """
        Build a Report object summarizing all accumulated evaluation counts.

        Parameters
        ----------
        creator : str
            Identifier of who ran the evaluation.
        experiment : str
            Experiment name or ID.
        model : str
            Model name or version.
        zero_division : float or None
            Passed through to Report for undefined metric behavior.
        metadata_extra : Any
            Additional metadata entries to include.

        Returns
        -------
        Report
            Contains confusion_matrix, metrics, classification_report, and metadata.
        """
        return Report(
            creator=creator,
            experiment=experiment,
            model=model,
            true_positive=self._true_positive,
            false_positive=self._false_positive,
            false_negative=self._false_negative,
            zero_division=zero_division,
            **metadata_extra
        )
