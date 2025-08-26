"""
evaluation.py

Stateful evaluator for LLM-extracted HPO labels.

Provides:
- Report: a placeholder stub that accepts any kwargs and does nothing, to be replaced by one holding the confusion matrix, metrics, classification report, and metadata.
- PhenotypeEvaluator: collects true_positive, false_positive, false_negative counts by comparing predicted labels to a ground truth Phenopacket.

Definitions:
- true_positive = a predicted label that exactly matches a label in the ground-truth set
- false_positive = a predicted label that does not appear in the ground-truth set
- false_negative = a ground-truth label that the model failed to predict, excluding false_positive
"""

import logging
from typing import List, Any, Optional

from notebooks.utils.phenopacket import Phenopacket
from notebooks.utils.report import Report

logger = logging.getLogger(__name__)


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
        return self._true_positive

    @property
    def false_positive(self) -> int:
        return self._false_positive

    @property
    def false_negative(self) -> int:
        return self._false_negative

    def check_phenotypes(
        self,
        experimentally_extracted_phenotypes: List[str],
        ground_truth_phenotypes: Phenopacket,
    ) -> None:
        """
        Compare a sample's predicted labels against its ground truth and update the running true_positive, false_positive, and false_negative counters.

            Parameters
            ----------
            experimentally_extracted_phenotypes
                The raw list of labels produced by the model for this sample.
            ground_truth_phenotypes
                A Phenopacket object whose `list_phenotypes()` method returns the true labels.
        """

        true_hpo_term_set = {
            label.strip().lower() for label in ground_truth_phenotypes.list_phenotypes()
        }
        experimental_hpo_term_set = {
            label.strip().lower() for label in experimentally_extracted_phenotypes
        }

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
        **metadata_extra: Any,
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
        metadata_extra : Any
            Additional metadata entries to include.

        Returns
        -------
        Report
            Pass the confusion_matrix, metrics, classification_report, and metadata into the real Report.
        """
        return Report(
            true_positive=self._true_positive,
            false_positive=self._false_positive,
            false_negative=self._false_negative,
            true_negative=0,
            creator=creator,
            experiment=experiment,
            model=model,
            **metadata_extra,
        )
