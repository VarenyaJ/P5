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
    """

    y_true: List[Any]
    y_pred: List[Any]
    metadata: Dict[str, Any]
    # These two fields are computed after __init__, not passed by the caller.
    confusion_matrix: List[List[int]] = field(init=False)
    metrics: Dict[str, float] = field(init=False)

    def __post_init__(self) -> None: