import logging
from typing import List, Dict, Any
from notebooks.utils.phenopacket import Phenopacket

from sklearn.metrics import (precision_score, recall_score, f1_score, classification_report)

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