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

logger = logging.getLogger(__name__)


class Report:
    def __init__(self, **kwargs):
        """
        Intentionally empty, removing all stuf functionality and saving for the report-class
        Placeholder stub for a future reporting class.

        This constructor accepts arbitrary keyword arguments but does nothing with them.
            In a follow-up PR, Report will be expanded to:
        - store the confusion matrix (TP, FP, FN, TN)
        - compute precision, recall, and F1
        - render a classification report string
        - include user-provided metadata (creator, experiment, model, etc.)

        Until then, this empty stub satisfies type checks and allows evaluator.report()
        calls to succeed without errors.
        """
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
        self,
        experimentally_extracted_phenotypes: List[str],
        ground_truth_phenotypes: Phenopacket,
    ) -> None:
        """
        Compare a sample's predicted labels against its ground truth and update the running true_positive, false_positive, and false_negative counters.

        Steps:
            1. Strip leading/trailing whitespace from each label.
            2. Build a set of ground-truth labels by calling `list_phenotypes()`.
            3. Build a set of predicted labels from the provided list.
            4. Compute:
                - TP as true_hpo_term_set ∩ experimental_hpo_term_set
                - FP as labels in experimental_hpo_term_set but not in true_hpo_term_set
                - FN as any true_hpo_term_set labels that were not predicted
            5. Add these to the cumulative totals.

            Parameters
            ----------
            experimentally_extracted_phenotypes
                The raw list of labels produced by the model for this sample.
            ground_truth_phenotypes
                A Phenopacket object whose `list_phenotypes()` method returns the true labels.
            """

        # 1) Normalize (strip + lowercase) and build sets
        true_hpo_term_set = {
            ground_truth_label.strip().lower()
            for ground_truth_label in ground_truth_phenotypes.list_phenotypes()
        }
        experimental_hpo_term_set = {
            experimental_label.strip().lower()
            for experimental_label in experimentally_extracted_phenotypes
        }

        # 4) Compute intersections and differences by set cardinality
        #    |A ? B| gives number of exact matches
        true_positive = len(true_hpo_term_set & experimental_hpo_term_set)

        #    |B - A| gives number of predicted labels not in truth
        false_positive = len(experimental_hpo_term_set - true_hpo_term_set)

        #    if |true| > |pred|, the excess truth slots were never filled -> FN
        false_negative = max(len(true_hpo_term_set) - len(experimental_hpo_term_set), 0)

        # 5) Update cumulative counters
        self._true_positive += true_positive
        self._false_positive += false_positive
        self._false_negative += false_negative

        # debug log of this sample's counts
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
