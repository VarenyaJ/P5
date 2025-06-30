import logging
from typing import List, Dict, Any
from notebooks.utils.phenopacket import Phenopacket

from sklearn.metrics import (
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

    def report(
        self, creator: str, experiment: str, model: str, **metadata_extra: Any
    ) -> Dict[str, Any]:
        """
        Compile the accumulated counts into a full evaluation summary.

        Computes:
          - confusion_matrix: [[TP, FP], [FN, 0]]
          - metrics: macro precision, recall, F1
          - classification_report: per-label table via sklearn
          - metadata: date-free dict you can JSON-dump or feed into Report later

        Parameters
        ----------
        creator : str
            Who ran this evaluation.
        experiment : str
            Experiment ID or name.
        model : str
            Model name or version.
        **metadata_extra : Any
            Any additional metadata entries to carry forward.

        Returns
        -------
        dict with keys:
          - "confusion_matrix": List[List[int]]
          - "metrics": {"precision", "recall", "f1_score"}
          - "classification_report": str
          - "metadata": dict
        """
        """
        1) Build the confusion matrix structure.
           Layout:
               [[TP, FP],
                [FN,  0 ]]
           - Row 0: actual positives
           - Row 1: actual negatives (we set TN=0 because TN is undefined here)
           - Col 0: predicted positives
           - Col 1: predicted negatives
        """
        confusion_matrix = [
            [self.tp, self.fp],
            [self.fn, 0],
        ]

        """
        2) Compute precision = TP / (TP + FP).
           If TP+FP == 0 (no predicted positives), define precision = 0.0 to avoid div-by-zero.
        """
        if (self.tp + self.fp) > 0:
            precision = self.tp / (self.tp + self.fp)
        else:
            precision = 0.0

        """
        3) Compute recall = TP / (TP + FN).
           If TP+FN == 0 (no actual positives), define recall = 0.0.
        """
        if (self.tp + self.fn) > 0:
            recall = self.tp / (self.tp + self.fn)
        else:
            recall = 0.0

        """
        4) Compute F1 score = 2 * (precision * recall) / (precision + recall).
           If precision+recall == 0, define f1_score = 0.0.
        """
        if (precision + recall) > 0:
            f1_score = 2 * precision * recall / (precision + recall)
        else:
            f1_score = 0.0

        """
        5) Package precision, recall, and F1 into a metrics dict for easy access.
        """
        metrics = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
        }

        """
        6) Construct synthetic y_true and y_pred lists so sklearn's classification_report
           can generate a per‐label breakdown:
             - For each TP: (1,1)
             - For each FN: (1,0)
             - For each FP: (0,1)
           Here, '1' means "label present", '0' means "label absent".
        """
        y_true = []
        y_pred = []

        """
        6a) Add one (1,1) entry for each true positive.
        """
        for _ in range(self.tp):
            y_true.append(1)
            y_pred.append(1)

        """
        6b) Add one (1,0) entry for each false negative.
        """
        for _ in range(self.fn):
            y_true.append(1)
            y_pred.append(0)

        """
        6c) Add one (0,1) entry for each false positive.
        """
        for _ in range(self.fp):
            y_true.append(0)
            y_pred.append(1)

        """
        7) Generate the human-readable classification report text
           using sklearn.metrics.classification_report.
           We label the classes "present" and "absent".
        """
        class_report_str = classification_report(
            y_true,
            y_pred,
            labels=[1, 0],
            target_names=["present", "absent"],
            zero_division=0,
        )

        """
        8) Assemble the metadata dict:
           - always include creator, experiment, model, and the raw TP/FP/FN counts
           - merge in any additional metadata passed via **metadata_extra
        """
        metadata = {
            "creator": creator,
            "experiment": experiment,
            "model": model,
            "TP": self.tp,
            "FP": self.fp,
            "FN": self.fn,
        }
        metadata.update(metadata_extra)

        """
        9) Return everything in one convenient dict.
        """
        return {
            "confusion_matrix": confusion_matrix,
            "metrics": metrics,
            "classification_report": class_report_str,
            "metadata": metadata,
        }

    #


#
