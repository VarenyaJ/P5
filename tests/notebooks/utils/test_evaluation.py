import json
import pytest
from pathlib import Path

from notebooks.utils.evaluation import PhenotypeEvaluator
from notebooks.utils.phenopacket import Phenopacket


@pytest.fixture
def simple_pp(tmp_path):
    """Write a minimal phenopacket with two HPO labels."""
    data = {
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000001", "label": "Phen1"}},
            {"type": {"id": "HP:0000002", "label": "Phen2"}},
        ]
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_perfect_prediction(simple_pp):
    ev = PhenotypeEvaluator()
    gt = Phenopacket.load_from_file(simple_pp)

    # predict both correctly
    ev.check_phenotypes(["Phen1", "Phen2"], gt)
    result = ev.report("alice", "exp1", "modelA")

    assert result["metadata"]["TP"] == 2
    assert result["metadata"]["FP"] == 0
    assert result["metadata"]["FN"] == 0

    m = result["metrics"]
    assert pytest.approx(1.0) == m["precision"]
    assert pytest.approx(1.0) == m["recall"]
    assert pytest.approx(1.0) == m["f1_score"]

    # classification_report should mention our labels 'present'/'absent'
    assert "present" in result["classification_report"]


def test_false_positive_and_miss(simple_pp):
    ev = PhenotypeEvaluator()
    gt = Phenopacket.load_from_file(simple_pp)

    # predict one right, one hallucination
    ev.check_phenotypes(["Phen1", "Fake"], gt)
    result = ev.report("bob", "exp2", "modelB")

    assert result["metadata"]["TP"] == 1
    assert result["metadata"]["FP"] == 1
    assert result["metadata"]["FN"] == 1

    m = result["metrics"]
    assert pytest.approx(0.5, rel=1e-6) == m["precision"]
    assert pytest.approx(0.5, rel=1e-6) == m["recall"]
    assert pytest.approx(0.5, rel=1e-6) == m["f1_score"]


def test_multiple_batches(simple_pp, tmp_path):
    ev = PhenotypeEvaluator()

    # first sample: one correct, one missed
    gt1 = Phenopacket.load_from_file(simple_pp)
    ev.check_phenotypes(["Phen1"], gt1)  # TP=1, FP=0, FN=1

    # second sample: one correct, one false positive
    data2 = {"phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "Phen1"}}]}
    p2 = tmp_path / "test2.json"
    p2.write_text(json.dumps(data2), encoding="utf-8")
    gt2 = Phenopacket.load_from_file(str(p2))
    ev.check_phenotypes(["Phen1", "Extra"], gt2)  # TP+=1, FP+=1, FN+=0

    result = ev.report("carol", "exp3", "modelC")
    md = result["metadata"]

    # Totals should now be TP=2, FP=1, FN=1
    assert md["TP"] == 2
    assert md["FP"] == 1
    assert md["FN"] == 1

    m = result["metrics"]
    # precision = 2/3, recall = 2/3, f1 = 2/3
    assert pytest.approx(2 / 3, rel=1e-6) == m["precision"]
    assert pytest.approx(2 / 3, rel=1e-6) == m["recall"]
    assert pytest.approx(2 / 3, rel=1e-6) == m["f1_score"]
