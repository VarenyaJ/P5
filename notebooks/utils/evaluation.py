"""
evaluation.py

Stateful evaluator for LLM-extracted HPO labels.

Provides:
- Report: holds confusion matrix, metrics, classification report, and metadata.
- PhenotypeEvaluator: collects true_positive, false_positive, false_negative counts
 by comparing predicted labels to a ground truth Phenopacket.
"""

import logging
from typing import List, Dict, Any

from notebooks.utils.phenopacket import Phenopacket
from sklearn.metrics import classification_report

from datetime import date

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Report:
   """
   Stub Report class for PhenotypeEvaluator.report().

   Collects confusion matrix, computed metrics, classification report text, and metadata for evaluation.

   Attributes
   ----------
   metadata : Dict[str, Any]
       Contains:
       - creator (str)
       - experiment (str)
       - model (str)
       - date (YYYY-MM-DD)
       - true_positive (int)
       - false_positive (int)
       - false_negative (int)
       - any extra metadata passed via **metadata_extra

   confusion_matrix : List[List[int]]
       2x2 matrix:
           [[TP, FP], [FN,  0]]
       where:
           TP = true_positive
           FP = false_positive
           FN = false_negative
           (True negatives undefined -> set to 0.)

   metrics : Dict[str, float]
       Macro-averaged metrics computed as:
           precision   = TP / (TP + FP)   if denom > 0 else 0.0
           recall      = TP / (TP + FN)   if denom > 0 else 0.0
           f1_score    = 2.(precision.recall)/(precision + recall)
           if (precision+recall)>0 else 0.0

   classification_report : str
       Text output from sklearn.metrics.classification_report using synthetic labels:
       - 'present' class -> positive instances
       - 'absent'  class -> negative instances
   """

   def __init__(
       self,
       creator: str,
       experiment: str,
       model: str,
       true_positive: int,
       false_positive: int,
       false_negative: int,
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

       #   2)  Build confusion matrix
       #   Layout rows->[actual positives, actual negatives], cols->[predicted positive, predicted negative]
       #   [[TP, FP],[FN,  0]]
       self.confusion_matrix: List[List[int]] = [
           [true_positive, false_positive],
           [false_negative, 0],
       ]

       # 3) Compute macro metrics
       if (true_positive + false_positive) > 0:
           precision = true_positive / (true_positive + false_positive)
       else:
           precision = 0.0

       if (true_positive + false_negative) > 0:
           recall = true_positive / (true_positive + false_negative)
       else:
           recall = 0.0

       if (precision + recall) > 0:
           f1_score = 2 * precision * recall / (precision + recall)
       else:
           f1_score = 0.0

       self.metrics: Dict[str, float] = {
           "precision": precision,
           "recall": recall,
           "f1_score": f1_score,
       }

       #   4)  Generate synthetic labels for classification_report
       #       For each true positive: (1,1)
       #       For each false negative:(1,0)
       #       For each false positive:(0,1)
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
   Stateful evaluator for LLM-extracted HPO labels. Accumulates HPO-extraction evaluation counts across multiple samples.

   Tracks:
       - True Positives (TP): correctly predicted label presence.
       - False Positives (FP): predicted labels absent in ground truth.
       - False Negatives (FN): ground truth labels not predicted.

   Methods
   -------
   check_phenotypes(predicted_labels, ground_truth_packet)
       Updates internal counts of true_positive, false_positive, false_negative.
   report(creator, experiment, model, **metadata_extra) -> Report
       Constructs and returns a Report summarizing all counts.
   """

   def __init__(self) -> None:
       """
       Initialize internal counters to zero.
       """
       self._true_positive: int = 0
       self._false_positive: int = 0
       self._false_negative: int = 0

   @property
   def true_positive(self) -> int:
       """
       Total true positives accumulated so far.
       """
       return self._true_positive

   @property
   def false_positive(self) -> int:
       """
       Total false positives accumulated so far.
       """
       return self._false_positive

   @property
   def false_negative(self) -> int:
       """
       Total false negatives accumulated so far.
       """
       return self._false_negative

   def check_phenotypes(
       self, hpo_labels: List[str], ground_truth_packet: Phenopacket
   ) -> None:
       """
       Compare a single sample's predicted HPO labels against the ground truth and update counts.

       Parameters
       ----------
       hpo_labels : list of str
           HPO label strings extracted by the LLM for this sample.
       ground_truth_packet : Phenopacket
           A Phenopacket instance loaded via Phenopacket.load_from_file(),
           containing the true HPO labels.

       Procedure
       ---------
       1) Extract sets
       2) Count/calculate true_positive, false_positive, and false_negative
       3) Accumulate into internal counters.
       """
       true_hpo_term_set = set(ground_truth_packet.list_phenotypes())
       experimental_hpo_term_set = set(hpo_labels)

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
       self, creator: str, experiment: str, model: str, **metadata_extra: Any
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
           Contains confusion_matrix, metrics, classification_report, and metadata.
       """
       return Report(
           creator=creator,
           experiment=experiment,
           model=model,
           true_positive=self._true_positive,
           false_positive=self._false_positive,
           false_negative=self._false_negative,
           **metadata_extra
       )