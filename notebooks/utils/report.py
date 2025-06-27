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