import logging
from typing import List, Dict, Any
from notebooks.utils.phenopacket import Phenopacket

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    classification_report,
)

logger = logging.getLogger(__name__)


class PhenotypeEvaluator:
    """
    Stateful evaluator for LLM-extracted HPO labels.

    Tracks:
        - True Positives (TP): correctly predicted HPO labels.
        - False Positives (FP): labels predicted but not actually present.
        - False Negatives (FN): true labels that were missed.

    TN is omitted (open vocabulary, infinite negatives).

    Attributes
    ----------
    tp : int
        Cumulative true positive count.
    fp : int
        Cumulative false positive count.
    fn : int
        Cumulative false negative count.
    """

    def __init__(self) -> None:
        self.tp = 0
        self.fp = 0
        self.fn = 0

    def check_phenotypes(
        self, hpo_labels: List[str], ground_truth_phenopacket: Phenopacket
    ) -> None:
        """
        Compare one sample’s predicted HPO labels against a ground-truth Phenopacket.

        Parameters
        ----------
        hpo_labels : list of str
            The HPO *label* strings the LLM will extract, e.g. ["Short stature", ...].
        ground_truth_phenopacket : Phenopacket
            A loaded Phenopacket instance containing the true labels.

        Notes
        -----
        - TP = |predicted ∩ true|
        - FP = |predicted != true|
        - FN = |true != predicted|
        """
        true_hpo_term_set = set(ground_truth_phenopacket.list_phenotypes())
        experimental_hpo_term_set = set(hpo_labels)

        tp = len(true_hpo_term_set & experimental_hpo_term_set)
        fp = len(experimental_hpo_term_set - true_hpo_term_set)
        fn = len(true_hpo_term_set - experimental_hpo_term_set)

        logger.debug("Sample evaluation → TP=%d, FP=%d, FN=%d", tp, fp, fn)

        self.tp += tp
        self.fp += fp
        self.fn += fn
