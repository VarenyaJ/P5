"""
evaluation.py

Stateful evaluator for LLM-extracted HPO labels.

Provides:
- Report: a placeholder stub that accepts any kwargs and does nothing, to be replaced by one holding the confusion matrix, metrics, classification report, and metadata.
- PhenotypeEvaluator: collects true_positive, false_positive, false_negative counts by comparing predicted labels to a ground truth Phenopacket.
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
        pass

class PhenotypeEvaluator:
    """
    Accumulates HPO-extraction evaluation counts across multiple samples.

    Methods
    -------
    check_phenotypes(experimentally_extracted_phenotypes, ground_truth_phenotypes)
        Updates internal counts of true_positive, false_positive, false_negative.
    report(creator, experiment, model, **metadata_extra) -> Report
        Constructs and returns a Report summarizing all counts.
    """

    def __init__(self) -> None:
        self._true_positive: int = 0
        self._false_positive: int = 0
        self._false_negative: int = 0

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
        self, experimentally_extracted_phenotypes: List[str], ground_truth_phenotypes: Phenopacket
    ) -> None:
        """
        Compare one sample’s predicted labels against its ground truth.

        Steps:
            1. Strip leading/trailing whitespace from each label.
            2. Build a set of ground‐truth labels by calling `list_phenotypes()`.
            3. Build a set of predicted labels from the provided list.
            4. Compute:
                - TP as the size of the intersection.
                - FP as labels in predicted but not in ground truth.
                - FN as any ground‐truth labels that were not predicted.
          5. Add these to the cumulative totals.

        Parameters
        ----------
        experimentally_extracted_phenotypes
            A list of strings output by the model for this sample.
        ground_truth_phenotypes
            A Phenopacket whose `list_phenotypes()` returns the true labels.
        """

        true_hpo_term_set = {label.strip() for label in ground_truth_phenotypes.list_phenotypes()}
        experimental_hpo_term_set = {label.strip() for label in experimentally_extracted_phenotypes}

        true_positive = len(true_hpo_term_set & experimental_hpo_term_set)
        false_positive = len(experimental_hpo_term_set - true_hpo_term_set)
        false_negative = max(len(true_hpo_term_set) - len(experimental_hpo_term_set), 0)

        self._true_positive += true_positive
        self._false_positive += false_positive
        self._false_negative += false_negative

        logger.debug(
            "Sample evaluation: TP=%d, FP=%d, FN=%d",
            true_positive,
            false_positive,
            false_negative,
        )

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
            A placeholder which should be replaced via PR to hold a confusion_matrix, metrics, classification_report, and metadata.
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
