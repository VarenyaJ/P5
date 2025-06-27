import json
import pytest
from pathlib import Path
from sklearn.metrics import precision_score, recall_score, f1_score
from notebooks.utils.report import Report

def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        Report.create([0, 1], [0], "A", "E1", "M1")