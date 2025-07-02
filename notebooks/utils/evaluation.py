"""
evaluation.py

Stateful evaluator for LLM-extracted HPO labels.

Tracks true positives (TP), false positives (FP), and false negatives (FN),
and assembles a Report summarizing performance.
"""

import logging
from typing import List, Dict, Any

from notebooks.utils.phenopacket import Phenopacket
from sklearn.metrics import classification_report

logger = logging.getLogger(__name__)


class Report:
   """
   Stub Report class for PhenotypeEvaluator.report().

   Collects confusion matrix, computed metrics, classification report text,
   and metadata for evaluation.
   """

   def __init__(
           self,
           creator: str,
           experiment: str,
           model: str,
           tp: int,
           fp: int,
           fn: int,
           **metadata_extra: Any
   ) -> None:
       """
       Initialize a Report stub with counts and metadata.

       Parameters
       ----------
       creator : str
           Identifier of who ran the evaluation.
       experiment : str
           Experiment name or ID.
       model : str
           Model name or version.
       tp : int
           Total true positives.
       fp : int
           Total false positives.
       fn : int
           Total false negatives.
       **metadata_extra : Any
           Additional metadata entries to include.
       """
       # Build metadata dict
       self.metadata: Dict[str, Any] = {
           "creator": creator,
           "experiment": experiment,
           "model": model,
           "TP": tp,
           "FP": fp,
           "FN": fn,
       }
       self.metadata.update(metadata_extra)

       # Confusion matrix layout:
       # [[TP, FP],
       #  [FN,  0 ]]
       self.confusion_matrix = [[tp, fp], [fn, 0]]

       # Compute macro precision, recall, and F1 score
       if tp + fp > 0:
           precision = tp / (tp + fp)
       else:
           precision = 0.0

       if tp + fn > 0:
           recall = tp / (tp + fn)
       else:
           recall = 0.0

       if precision + recall > 0:
           f1 = 2 * precision * recall / (precision + recall)
       else:
           f1 = 0.0

       self.metrics = {
           "precision": precision,
           "recall": recall,
           "f1_score": f1,
       }

       # Build synthetic y_true/y_pred lists for sklearn's classification_report
       y_true = [1] * tp + [1] * fn + [0] * fp
       y_pred = [1] * tp + [0] * fn + [1] * fp

       self.classification_report = classification_report(
           y_true,
           y_pred,
           labels=[1, 0],
           target_names=["present", "absent"],
           zero_division=0,
       )


class PhenotypeEvaluator:
   """
   Stateful evaluator for LLM-extracted HPO labels.

   Tracks:
       - True Positives (TP): correctly predicted label presence.
       - False Positives (FP): predicted labels absent in ground truth.
       - False Negatives (FN): ground truth labels not predicted.
   """

   def __init__(self) -> None:
       """
       Initialize the evaluator with zeroed counts.
       """
       # Private counters to prevent external mutation
       self._tp = 0
       self._fp = 0
       self._fn = 0

   @property
   def tp(self) -> int:
       """
       Total true positives accumulated.
       """
       return self._tp

   @property
   def fp(self) -> int:
       """
       Total false positives accumulated.
       """
       return self._fp

   @property
   def fn(self) -> int:
       """
       Total false negatives accumulated.
       """
       return self._fn

   def check_phenotypes(
           self,
           hpo_labels: List[str],
           ground_truth_phenopacket: Phenopacket,
   ) -> None:
       """
       Compare one sample's predicted HPO labels against a ground-truth Phenopacket.

       Parameters
       ----------
       hpo_labels : List[str]
           The HPO label strings predicted by the LLM.
       ground_truth_phenopacket : Phenopacket
           A loaded Phenopacket instance containing the true labels.

       Notes
       -----
       - TP = |predicted ? true|
       - FP = |predicted \\ true|
       - FN = |true \\ predicted|
       """
       true_set = set(ground_truth_phenopacket.list_phenotypes())
       pred_set = set(hpo_labels)

       tp = len(true_set & pred_set)
       fp = len(pred_set - true_set)
       fn = len(true_set - pred_set)

       logger.debug("Sample evaluation -> TP=%d, FP=%d, FN=%d", tp, fp, fn)

       self._tp += tp
       self._fp += fp
       self._fn += fn

   def report(
           self,
           creator: str,
           experiment: str,
           model: str,
           **metadata_extra: Any
   ) -> Report:
       """
       Compile the accumulated counts into a Report instance.

       Parameters
       ----------
       creator : str
           Who ran this evaluation.
       experiment : str
           Experiment ID or name.
       model : str
           Model name or version.
       **metadata_extra : Any
           Additional metadata entries to carry forward.

       Returns
       -------
       Report
           A Report object summarizing confusion matrix, metrics,
           classification report, and metadata.
       """
       return Report(
           creator,
           experiment,
           model,
           self._tp,
           self._fp,
           self._fn,
           **metadata_extra
       )